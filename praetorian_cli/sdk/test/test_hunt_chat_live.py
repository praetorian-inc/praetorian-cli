import asyncio
from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from praetorian_cli.sdk.entities.conversations import _transcript
from praetorian_cli.ui.hunt_chat_live import (
    MAX_TOOL_DETAIL_CHARACTERS,
    HuntChatApp,
    HuntChatSession,
    build_live_message,
    build_live_tool_activity,
    format_live_tool_details,
    group_hunt_tool_messages,
    run_live_hunt_chat,
)


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

    def get(self, conversation_id):
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

            await app.action_older_history()
            assert session.history_page == 1
            await app.action_next_conversation()
            assert session.selected_id == 'child'
            assert app.query_one('#composer').disabled is True
            app.action_cancel_chat()
            await pilot.pause()

    asyncio.run(exercise_app())


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
