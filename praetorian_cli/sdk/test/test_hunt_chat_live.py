import asyncio
import threading
import time
from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from praetorian_cli.sdk.entities.conversations import _transcript
from praetorian_cli.ui import hunt_chat_live
from praetorian_cli.ui.hunt_chat_live import (
    MAX_TOOL_DETAIL_CHARACTERS,
    HuntChatApp,
    HuntChatSession,
    ToolActivity,
    build_live_message,
    build_live_tool_activity,
    format_live_tool_details,
    group_hunt_tool_messages,
    run_live_hunt_chat,
)
from praetorian_cli.ui.textual_refresh import RefreshModal


def _conversation(uuid, status='idle', parent='self', topic=None):
    return {
        'uuid': uuid,
        'status': status,
        'parent_id': parent,
        'topic': topic or f'Conversation {uuid}',
        'created': '2026-01-01T00:00:00Z',
    }


class FakeHunts:
    def __init__(self):
        self.conversations = [
            _conversation('root', status='active'),
            _conversation('child', parent='root'),
        ]
        self.interactions = []
        self.fail_conversations = False

    def list_conversations(self, _hunt_id):
        if self.fail_conversations:
            raise ConnectionError('temporary disconnect')
        return list(self.conversations), None

    def list_interactions(self, _hunt_id, status='pending'):
        assert status == 'pending'
        return list(self.interactions)


class FakeConversations:
    def __init__(self):
        self.transcripts = {
            'root': {'messages': []},
            'child': {'messages': []},
        }
        self.sent = []
        self.calls = []

    def get(self, conversation_id):
        self.calls.append(conversation_id)
        return self.transcripts[conversation_id]

    def send_message(self, conversation_id, message):
        self.sent.append((conversation_id, message))
        return {'status': 'queued'}


def _session(page_size=25):
    sdk = SimpleNamespace(
        hunts=FakeHunts(),
        conversations=FakeConversations(),
    )
    session = HuntChatSession(sdk, 'hunt-1', page_size=page_size)
    session.refresh(raise_errors=True)
    return session, sdk


def test_live_refresh_preserves_selection_and_recovers_after_disconnect():
    session, sdk = _session()
    sdk.conversations.transcripts['child'] = {
        'messages': [{'role': 'chariot', 'content': 'initial'}],
    }
    assert session.select_conversation('child') is True

    sdk.hunts.fail_conversations = True
    assert session.refresh() is False
    assert session.selected_id == 'child'
    assert session.messages[0]['content'] == 'initial'
    assert session.consecutive_failures == 1
    assert 'temporary disconnect' in session.error

    sdk.hunts.fail_conversations = False
    sdk.conversations.transcripts['child'] = {
        'messages': [
            {'role': 'chariot', 'content': 'initial'},
            {'role': 'chariot', 'content': 'live update'},
        ],
    }
    assert session.refresh() is True
    assert session.selected_id == 'child'
    assert session.messages[-1]['content'] == 'live update'
    assert session.consecutive_failures == 0
    assert session.error == ''


def test_switching_between_visited_chats_reuses_cached_transcripts():
    session, sdk = _session()

    assert session.select_conversation('child') is True
    assert session.select_conversation('root') is True
    assert session.select_conversation('child') is True

    assert sdk.conversations.calls == ['root', 'child']


def test_history_pages_cover_the_complete_transcript_and_track_new_messages():
    session, sdk = _session(page_size=10)
    sdk.conversations.transcripts['root'] = {
        'messages': [
            {'role': 'chariot', 'content': f'message-{index}'}
            for index in range(23)
        ],
    }
    session.refresh()

    assert [row['content'] for row in session.visible_messages] == [
        f'message-{index}' for index in range(13, 23)
    ]
    assert session.older_history() is True
    assert [row['content'] for row in session.visible_messages] == [
        f'message-{index}' for index in range(3, 13)
    ]
    assert session.older_history() is True
    assert [row['content'] for row in session.visible_messages] == [
        'message-0', 'message-1', 'message-2'
    ]
    assert session.older_history() is False

    sdk.conversations.transcripts['root']['messages'].append({
        'role': 'chariot',
        'content': 'message-23',
    })
    session.refresh()
    assert session.history_page == 2
    assert session.unseen_messages == 1
    assert session.newer_history() is True
    assert session.newer_history() is True
    assert session.unseen_messages == 0


def test_guidance_is_revalidated_for_active_roots_only():
    session, sdk = _session()

    session.send_guidance('Focus on SMB')
    assert sdk.conversations.sent == [('root', 'Focus on SMB')]

    sdk.hunts.conversations[1]['status'] = 'active'
    session.refresh()
    session.select_conversation('child')
    assert session.can_guide is False
    with pytest.raises(ValueError, match='root Hunt iteration'):
        session.send_guidance('Do not send this')

    session.select_conversation('root')
    sdk.hunts.conversations[0]['status'] = 'idle'
    session.refresh()
    assert session.can_guide is False
    with pytest.raises(ValueError, match='active Hunt iteration'):
        session.send_guidance('Do not send this either')
    assert sdk.conversations.sent == [('root', 'Focus on SMB')]


def test_tool_responses_are_grouped_bounded_and_secret_fields_are_redacted():
    messages = [
        {
            'role': 'tool call',
            'toolUseId': 'tool-1',
            'tool': {
                'name': 'authenticate',
                'input': {'username': 'operator', 'password': 'never-render'},
            },
        },
        {
            'role': 'tool response',
            'toolUseId': 'tool-1',
            'content': {
                'access_token': 'also-never-render',
                'output': '\x1b[31m' + ('x' * 9000),
            },
            'screenshots': [{
                'filename': '/tmp/capture.png',
                'url': 'https://signed.example/tool-secret',
                'contentType': 'image/png',
            }],
        },
    ]

    grouped = group_hunt_tool_messages(messages)
    rendered = format_live_tool_details(grouped[0]['tool'])
    output = StringIO()
    Console(file=output, width=100, color_system=None).print(
        build_live_tool_activity(grouped[0], expanded=True)
    )
    rendered_panel = output.getvalue()

    assert len(grouped) == 1
    assert grouped[0]['tool']['response'] == messages[1]['content']
    assert 'never-render' not in rendered
    assert 'also-never-render' not in rendered
    assert '[redacted]' in rendered
    assert '\x1b' not in rendered
    assert len(rendered) <= MAX_TOOL_DETAIL_CHARACTERS
    assert 'Screenshot: capture.png' in rendered_panel
    assert 'signed.example' not in rendered_panel


def test_markdown_attachment_rendering_uses_metadata_without_urls_or_payloads():
    message = {
        'role': 'chariot',
        'content': '# Result\n\n**Confirmed** finding.',
        'attachments': [{
            'filename': '/tmp/evidence/screenshot.png',
            'contentType': 'image/png',
            'size': 1024,
            'width': 800,
            'height': 600,
            'url': 'https://signed.example/secret-token',
            'data': 'RAW-PAYLOAD',
        }],
    }
    output = StringIO()
    Console(file=output, width=100, color_system=None).print(
        build_live_message(message)
    )
    rendered = output.getvalue()

    assert 'Result' in rendered
    assert 'Confirmed' in rendered
    assert 'Screenshot: screenshot.png' in rendered
    assert 'image/png' in rendered
    assert '800×600' in rendered
    assert '/tmp/evidence' not in rendered
    assert 'signed.example' not in rendered
    assert 'RAW-PAYLOAD' not in rendered


def test_transcript_keeps_only_safe_attachment_metadata():
    transcript = _transcript('root', {}, [
        {
            'key': '#message#root#1',
            'role': 'chariot',
            'content': 'Evidence attached',
            'attachments': [{
                'filename': '/private/tmp/screenshot.png',
                'contentType': 'image/png',
                'url': 'https://signed.example/private',
                'data': 'RAW-DATA',
            }],
        },
        {
            'key': '#message#root#2',
            'role': 'tool call',
            'toolUseContent': '{"Name":"browser","ToolUseID":"tool-1"}',
        },
        {
            'key': '#message#root#3',
            'role': 'tool response',
            'toolUseId': 'tool-1',
            'content': '{}',
            'screenshots': [{
                'filename': '/private/tmp/tool.png',
                'url': 'https://signed.example/tool',
            }],
        },
    ])

    assert transcript['messages'][0]['attachments'] == [{
        'kind': 'screenshot',
        'name': 'screenshot.png',
        'mediaType': 'image/png',
    }]
    assert transcript['messages'][1]['tool']['attachments'] == [{
        'kind': 'screenshot',
        'name': 'tool.png',
    }]
    assert 'signed.example' not in str(transcript)
    assert 'RAW-DATA' not in str(transcript)


def test_fullscreen_app_mounts_navigation_pages_and_read_only_composer():
    session, sdk = _session(page_size=2)
    sdk.conversations.transcripts['root'] = {
        'messages': [
            {'role': 'chariot', 'content': f'message-{index}'}
            for index in range(3)
        ],
    }
    sdk.hunts.interactions = [{
        'kind': 'approval',
        'status': 'pending',
        'conversationId': 'child',
        'requestId': 'approval-1',
    }]
    session.refresh()

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert len(app.query('#conversation-list > ListItem')) == 2
            assert app.query_one('#composer').disabled is False
            assert 'PENDING INTERACTION' in str(
                app.query_one('#interaction-status').render()
            )
            await asyncio.sleep(0.02)
            assert 'child' not in session.transcript_cache
            assert app.query_one('#transcript').__class__.__name__ == 'VerticalScroll'

            await pilot.press('pageup')
            await pilot.pause()
            assert session.history_page == 1
            await pilot.press('pagedown')
            await pilot.pause()
            assert session.history_page == 0

            calls_before_switch = len(sdk.conversations.calls)
            await pilot.press('down')
            deadline = time.monotonic() + 1
            while session.selected_id != 'child' and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert session.selected_id == 'child'
            assert len(sdk.conversations.calls) == calls_before_switch + 1
            assert app.query_one('#composer').disabled is True
            await pilot.press('up')
            await pilot.pause()
            assert session.selected_id == 'root'

            await pilot.press('f8')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise_app()) == 'review-interactions'


def test_tool_details_show_loading_and_collapse_to_original_height(monkeypatch):
    session, _sdk_client = _session()
    session.transcript = {
        'messages': [{
            'role': 'tool call',
            'tool': {
                'name': 'analyze_iteration',
                'input': {'target': 'example.test'},
                'response': {'output': '\n'.join(f'line-{i}' for i in range(30))},
            },
        }],
    }
    original_builder = hunt_chat_live.build_live_tool_activity
    expansion_started = threading.Event()
    allow_expansion = threading.Event()

    def delayed_builder(message, expanded=False):
        if expanded:
            expansion_started.set()
            allow_expansion.wait(timeout=2)
        return original_builder(message, expanded)

    monkeypatch.setattr(
        hunt_chat_live,
        'build_live_tool_activity',
        delayed_builder,
    )

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            tool = app.query_one(ToolActivity)
            tool.focus()
            await pilot.pause()
            collapsed_height = tool.size.height

            await pilot.press('enter')
            while not expansion_started.is_set():
                await asyncio.sleep(0.005)
            assert 'Loading details' in str(
                app.query_one('#interaction-status').render()
            )
            allow_expansion.set()
            deadline = time.monotonic() + 1
            while not tool.expanded and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert tool.size.height > collapsed_height

            await pilot.press('space')
            deadline = time.monotonic() + 1
            while tool.expanded and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert tool.size.height == collapsed_height
            assert 'Loading details' not in str(
                app.query_one('#interaction-status').render()
            )

    asyncio.run(exercise_app())


def test_live_chat_escape_returns_to_previous_screen():
    session, _sdk_client = _session()
    session.refresh()

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press('escape')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise_app()) == 'cancelled'


def test_live_chat_arrow_navigation_shows_loading_feedback():
    session, _sdk_client = _session()
    session.refresh()
    original_move = session.move_selection
    move_started = threading.Event()
    allow_move = threading.Event()

    def delayed_move(delta):
        move_started.set()
        allow_move.wait(timeout=2)
        return original_move(delta)

    session.move_selection = delayed_move

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press('down')
            while not move_started.is_set():
                await asyncio.sleep(0.005)
            assert 'Loading' in str(
                app.query_one('#interaction-status').render()
            )
            assert session.selected_id == 'root'
            allow_move.set()
            deadline = time.monotonic() + 1
            while session.selected_id != 'child' and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert session.selected_id == 'child'
            assert 'Loading' not in str(
                app.query_one('#interaction-status').render()
            )

    asyncio.run(exercise_app())


def test_live_chat_manual_refresh_uses_blocking_spinner_modal():
    session, _sdk_client = _session()
    session.refresh()
    original_refresh = session.refresh
    refresh_started = threading.Event()
    allow_refresh = threading.Event()

    def delayed_refresh(*args, **kwargs):
        refresh_started.set()
        allow_refresh.wait(timeout=2)
        return original_refresh(*args, **kwargs)

    session.refresh = delayed_refresh

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press('ctrl+r')
            while not refresh_started.is_set():
                await asyncio.sleep(0.005)
            modal = app.screen
            assert isinstance(modal, RefreshModal)
            assert 'REFRESHING CHAT' in str(
                modal.query_one('#refresh-message').render()
            )
            await pilot.press('ctrl+n')
            assert session.selected_id == 'root'
            allow_refresh.set()
            deadline = time.monotonic() + 1
            while isinstance(app.screen, RefreshModal) and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            assert not isinstance(app.screen, RefreshModal)

    asyncio.run(exercise_app())


def test_live_chat_never_refreshes_automatically():
    session, sdk_client = _session()
    session.refresh()
    conversation_calls = list(sdk_client.conversations.calls)

    async def exercise_app():
        app = HuntChatApp(session)
        async with app.run_test(size=(100, 30)):
            await asyncio.sleep(0.2)
            assert sdk_client.conversations.calls == conversation_calls

    asyncio.run(exercise_app())


def test_live_runner_shows_feedback_while_loading_initial_chat_state():
    _session_state, sdk = _session()
    feedback = []

    class Status:
        def __enter__(self):
            feedback.append('entered')

        def __exit__(self, *_args):
            return False

    class Console:
        def status(self, message, spinner):
            feedback.extend([message, spinner])
            return Status()

    class FakeApp:
        def __init__(self, _session):
            pass

        def run(self):
            return 'cancelled'

    run_live_hunt_chat(
        sdk,
        'hunt-1',
        console=Console(),
        app_factory=FakeApp,
    )

    assert feedback == ['Loading chats…', 'dots', 'entered']


def test_live_runner_rejects_a_workflow_prefix_when_exact_id_is_required():
    _session_state, sdk = _session()

    with pytest.raises(ValueError, match='does not belong'):
        run_live_hunt_chat(
            sdk,
            'hunt-1',
            requested_id='chi',
            exact_requested_id=True,
            app_factory=lambda _session: pytest.fail(
                'chat app must not open for an inexact workflow reference'
            ),
        )


def test_live_runner_reuses_shared_interaction_reviewer_and_cancels_cleanly():
    session, sdk = _session()
    sdk.hunts.interactions = [{
        'kind': 'approval',
        'status': 'pending',
        'conversationId': 'root',
        'requestId': 'approval-1',
    }]
    outcomes = iter(['review-interactions', 'cancelled'])
    app_sessions = []
    reviewed = []

    class FakeApp:
        def __init__(self, current_session):
            app_sessions.append(current_session)

        def run(self):
            return next(outcomes)

    result = run_live_hunt_chat(
        sdk,
        'hunt-1',
        review_interactions=lambda rows: reviewed.extend(rows),
        app_factory=FakeApp,
    )

    assert result.selected_id == 'root'
    assert len(app_sessions) == 2
    assert app_sessions[0] is app_sessions[1]
    assert [row['requestId'] for row in reviewed] == ['approval-1']
