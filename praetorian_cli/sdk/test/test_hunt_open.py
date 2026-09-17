import asyncio
import threading
import time
from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from praetorian_cli.ui import hunt_open
from praetorian_cli.ui.hunt_memory import MEMORY_REFRESH_MAX_PAGES
from praetorian_cli.ui.hunt_open import (
    HUNT_OPEN_REFRESH_MAX_PAGES,
    HUNT_OPEN_VIEWS,
    HuntOpenApp,
    HuntOpenSession,
    build_hunt_open_overview,
    run_hunt_open,
)
from praetorian_cli.ui.textual_refresh import RefreshModal


HUNT_ID = 'hunt-1'


def _conversation(identifier, status='idle', parent='self'):
    return {
        'uuid': identifier,
        'status': status,
        'parent_id': parent,
        'title': f'Agent {identifier}',
        'created': '2026-09-14T12:00:00Z',
    }


class FakeHunts:
    def __init__(self):
        self.hunt = {
            'uuid': HUNT_ID,
            'status': 'active',
            'agent': 'hannibal',
            'findingsCount': 1,
            'iterationCount': 1,
            'prompt': 'Assess exposed services',
            'scope': ['#asset#example.com#192.0.2.10'],
        }
        self.calls = []
        self.findings = [{
            'key': '#risk#example.com#finding',
            'title': 'Exposed admin service',
            'dns': 'example.com',
            'status': 'OH',
            'statusLabel': 'Open High',
        }]
        self.workflows = [{
            'run_id': 'run-1',
            'status': 'running',
            'created': '2026-09-14T12:00:00Z',
            'steps': [],
        }]
        self.conversations = [
            _conversation('root', status='active'),
            _conversation('child', parent='root'),
        ]
        self.interactions = [{
            'kind': 'approval',
            'status': 'pending',
            'conversationId': 'child',
            'requestId': 'approval-1',
        }]
        self.memory_items = [
            {'title': 'alpha.md', 'updated': 'today'},
            {'title': 'beta.md', 'updated': 'today'},
        ]
        self.memory_content = {
            'alpha.md': 'alpha',
            'beta.md': 'beta',
        }
        self.log = 'iteration completed'

    def get(self, hunt_id):
        self.calls.append(('get', hunt_id))
        return dict(self.hunt) if hunt_id == HUNT_ID else None

    def get_cost(self, hunt_id):
        self.calls.append(('cost', hunt_id))
        return {
            'currency': 'USD',
            'total': {'cost': 1.25, 'total_tokens': 100},
        }

    def list_root_conversations(self, hunt_id, pages=1):
        self.calls.append(('roots', hunt_id, pages))
        return [dict(self.conversations[0])], None

    def endpoint_execution_status(self, hunt):
        self.calls.append(('endpoint', hunt['uuid']))
        return {'sessions': [], 'tasks': []}

    def list_findings(self, hunt_id, pages=1):
        self.calls.append(('findings', hunt_id, pages))
        return [dict(row) for row in self.findings], None

    def list_workflow_runs(self, hunt_id, pages=1):
        self.calls.append(('workflows', hunt_id, pages))
        return [dict(row) for row in self.workflows], None

    def list_conversations(self, hunt_id, pages=1):
        self.calls.append(('conversations', hunt_id, pages))
        return [dict(row) for row in self.conversations], None

    def list_interactions(self, hunt_id, status='pending', pages=1):
        self.calls.append(('interactions', hunt_id, status, pages))
        return [dict(row) for row in self.interactions]

    def list_memory(self, hunt_id, pages=1):
        self.calls.append(('memory', hunt_id, pages))
        return [dict(row) for row in self.memory_items], None

    def get_memory(self, hunt_id, title):
        self.calls.append(('memory-item', hunt_id, title))
        return self.memory_content[title]

    def get_log(self, hunt_id):
        self.calls.append(('log', hunt_id))
        return self.log

    def pause(self, hunt_id):
        self.calls.append(('pause', hunt_id))
        self.hunt['status'] = 'paused'

    def resume(self, hunt_id):
        self.calls.append(('resume', hunt_id))
        self.hunt['status'] = 'active'

    def stop(self, hunt_id):
        self.calls.append(('stop', hunt_id))
        self.hunt['status'] = 'stopped'


class FakeConversations:
    def __init__(self):
        self.transcripts = {
            'root': {'messages': [{'role': 'chariot', 'content': 'working'}]},
            'child': {'messages': [{'role': 'agent', 'content': 'checking'}]},
        }
        self.sent = []

    def get(self, conversation_id):
        return self.transcripts[conversation_id]

    def send_message(self, conversation_id, message):
        self.sent.append((conversation_id, message))
        return {'status': 'queued'}


def _sdk():
    return SimpleNamespace(
        hunts=FakeHunts(),
        conversations=FakeConversations(),
    )


def _render(renderable):
    output = StringIO()
    Console(file=output, width=120, color_system=None).print(renderable)
    return output.getvalue()


def test_every_declared_hunt_open_binding_has_an_action_handler():
    app = HuntOpenApp(HuntOpenSession(_sdk(), HUNT_ID))

    missing = [
        binding.action
        for binding in app.BINDINGS
        if not callable(getattr(app, f'action_{binding.action}', None))
    ]

    assert missing == []


def test_session_refreshes_only_selected_view_with_bounded_reads():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID, initial_hunt=sdk.hunts.hunt)

    assert session.refresh('overview', raise_errors=True) is True
    assert ('roots', HUNT_ID, HUNT_OPEN_REFRESH_MAX_PAGES) in sdk.hunts.calls
    assert ('findings', HUNT_ID, HUNT_OPEN_REFRESH_MAX_PAGES) in sdk.hunts.calls
    assert not any(call[0] == 'workflows' for call in sdk.hunts.calls)
    assert not any(call[0] == 'memory' for call in sdk.hunts.calls)

    session.refresh('workflow', raise_errors=True)
    assert sdk.hunts.calls[-1] == (
        'workflows', HUNT_ID, HUNT_OPEN_REFRESH_MAX_PAGES,
    )
    assert session.loaded_views == {'overview', 'workflow'}


def test_refresh_preserves_workflow_memory_and_chat_selection():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)

    session.refresh('workflow', raise_errors=True)
    sdk.hunts.workflows.insert(0, {
        'run_id': 'run-2',
        'status': 'completed',
        'created': '2026-09-14T13:00:00Z',
        'steps': [],
    })
    session.workflow_browser.cursor = 0
    session.refresh('workflow', raise_errors=True)
    assert session.workflow_browser.current['run_id'] == 'run-1'

    session.refresh('memory', raise_errors=True)
    session.memory_browser.move(1)
    sdk.hunts.memory_items.insert(0, {'title': 'aardvark.md'})
    sdk.hunts.memory_content['aardvark.md'] = 'new'
    session.refresh('memory', raise_errors=True)
    assert session.memory_browser.current_title == 'beta.md'

    session.refresh('chat', raise_errors=True)
    assert session.chat_session.select_conversation('child') is True
    sdk.conversations.transcripts['child']['messages'].append({
        'role': 'agent', 'content': 'still checking',
    })
    session.refresh('chat', raise_errors=True)
    assert session.chat_session.selected_id == 'child'
    assert session.chat_session.messages[-1]['content'] == 'still checking'


def test_workflow_collapse_and_step_selection_survive_refresh():
    sdk = _sdk()
    sdk.hunts.workflows[0]['steps'] = [
        {'kind': 'agent', 'conversation_id': 'root'},
        {'kind': 'agent', 'conversation_id': 'child'},
    ]
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('workflow', raise_errors=True)
    browser = session.workflow_browser
    browser.enter()
    browser.move(1)
    assert browser.current_conversation_id == 'child'
    browser.leave_steps()
    browser.toggle()
    assert browser.expanded == set()

    session.refresh('workflow', raise_errors=True)

    assert session.workflow_browser.expanded == set()
    assert session.workflow_browser.current_conversation_id == 'child'
    assert session.workflow_browser.step_mode is False


def test_rendered_view_is_reused_until_its_state_changes():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('workflow', raise_errors=True)
    cached = session.render('workflow')
    original_builder = session._build_view
    session._build_view = lambda _view: (_ for _ in ()).throw(
        AssertionError('cached view must not be rebuilt')
    )

    assert session.render('workflow') is cached

    session._build_view = original_builder
    session.invalidate_view('workflow')
    assert session.render('workflow') is not cached


def test_cached_tab_switch_does_not_reload_view_data():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    session.refresh('workflow', raise_errors=True)
    session.select_view('overview')
    workflow_calls = sum(
        1 for call in sdk.hunts.calls if call[0] == 'workflows'
    )

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('3')
            await pilot.pause()
            assert session.active_view == 'workflow'
            assert sum(
                1 for call in sdk.hunts.calls if call[0] == 'workflows'
            ) == workflow_calls

    asyncio.run(exercise())


def test_all_required_views_render_and_attack_paths_are_not_a_tab():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    for view in HUNT_OPEN_VIEWS:
        session.refresh(view)
        assert _render(session.render(view)).strip()

    combined = _render(build_hunt_open_overview(session))
    assert 'Assess exposed services' in combined
    assert HUNT_OPEN_VIEWS == (
        'overview', 'vulnerabilities', 'workflow',
        'log', 'memory', 'chat', 'approvals',
    )
    assert 'attack' not in ' '.join(HUNT_OPEN_VIEWS)


def test_chat_steering_reuses_session_active_root_revalidation():
    sdk = _sdk()
    authorization_calls = []

    def authorize(hunt_id):
        authorization_calls.append(hunt_id)
        return sdk.hunts.get(hunt_id)

    session = HuntOpenSession(sdk, HUNT_ID, authorize_hunt=authorize)
    session.refresh('chat', raise_errors=True)
    calls_before_guidance = len(authorization_calls)

    session.chat_session.send_guidance('Focus on authentication')

    assert sdk.conversations.sent == [('root', 'Focus on authentication')]
    assert ('conversations', HUNT_ID, HUNT_OPEN_REFRESH_MAX_PAGES) in sdk.hunts.calls
    assert len(authorization_calls) > calls_before_guidance


def test_session_pause_and_resume_use_shared_sdk_lifecycle_methods():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)

    session.perform_lifecycle('pause')
    assert session.status == 'paused'
    session.perform_lifecycle('resume')
    assert session.status == 'active'

    assert ('pause', HUNT_ID) in sdk.hunts.calls
    assert ('resume', HUNT_ID) in sdk.hunts.calls


def test_runner_confirms_stop_and_revalidates_before_mutation(monkeypatch):
    sdk = _sdk()
    monkeypatch.setattr(hunt_open, 'supports_fullscreen_hunt_open', lambda: True)
    outcomes = iter(['stop', 'close'])
    authorization_calls = []

    class FakeApp:
        def __init__(self, _session):
            pass

        def run(self):
            return next(outcomes)

    def authorize(hunt_id):
        authorization_calls.append(hunt_id)
        return sdk.hunts.get(hunt_id)

    session = run_hunt_open(
        sdk,
        HUNT_ID,
        authorize_hunt=authorize,
        confirm_stop=lambda _message: False,
        app_factory=FakeApp,
    )

    assert not any(call[0] == 'stop' for call in sdk.hunts.calls)
    assert session.notice == 'Stop cancelled.'
    assert authorization_calls

    outcomes = iter(['stop', 'close'])
    run_hunt_open(
        sdk,
        HUNT_ID,
        authorize_hunt=authorize,
        confirm_stop=lambda _message: True,
        app_factory=FakeApp,
    )
    assert ('stop', HUNT_ID) in sdk.hunts.calls
    assert len(authorization_calls) >= 4


def test_runner_shows_feedback_between_fullscreen_views_and_network_actions(
    monkeypatch,
):
    sdk = _sdk()
    monkeypatch.setattr(hunt_open, 'supports_fullscreen_hunt_open', lambda: True)
    outcomes = iter(['chat', 'pause', 'resume', 'close'])
    feedback = []

    class Status:
        def __init__(self, message):
            self.message = message

        def __enter__(self):
            feedback.append(self.message)

        def __exit__(self, *_args):
            return False

    class FeedbackConsole:
        def status(self, message, spinner):
            assert spinner == 'dots'
            return Status(message)

    class FakeApp:
        def __init__(self, _session):
            pass

        def run(self):
            return next(outcomes)

    run_hunt_open(
        sdk,
        HUNT_ID,
        console=FeedbackConsole(),
        app_factory=FakeApp,
        live_chat_runner=lambda *_args, **_kwargs: None,
    )

    assert feedback == [
        'Loading Hunt overview…',
        'Pausing Hunt…',
        'Resuming Hunt…',
    ]


def test_runner_reuses_bounded_live_chat_and_memory_interfaces(monkeypatch):
    sdk = _sdk()
    monkeypatch.setattr(hunt_open, 'supports_fullscreen_hunt_open', lambda: True)
    outcomes = iter(['chat', 'memory', 'memory-new', 'close'])
    chat_calls = []
    memory_calls = []

    class FakeApp:
        def __init__(self, session):
            self.session = session

        def run(self):
            outcome = next(outcomes)
            if outcome == 'chat':
                self.session.active_view = 'chat'
                self.session.requested_chat_id = 'child'
            elif outcome == 'memory':
                self.session.active_view = 'memory'
            return outcome

    run_hunt_open(
        sdk,
        HUNT_ID,
        console=Console(file=StringIO()),
        confirm_stop=lambda _message: True,
        app_factory=FakeApp,
        live_chat_runner=lambda *args, **kwargs: chat_calls.append(
            (args, kwargs)
        ),
        memory_browser=lambda *args, **kwargs: memory_calls.append(
            (args, kwargs)
        ),
    )

    assert chat_calls[0][0] == (sdk, HUNT_ID)
    assert chat_calls[0][1]['request_pages'] == HUNT_OPEN_REFRESH_MAX_PAGES
    assert chat_calls[0][1]['requested_id'] == 'child'
    assert not any(call[0] == 'conversations' for call in sdk.hunts.calls)
    assert len(memory_calls) == 2
    assert memory_calls[0][0][1:] == (sdk.hunts, HUNT_ID)
    assert memory_calls[0][1] == {}
    assert memory_calls[1][0][1:] == (sdk.hunts, HUNT_ID)
    assert memory_calls[1][1] == {'start_new': True}


def test_fullscreen_app_polls_interactions_only_on_selected_approvals_tab():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    assert session.pending_interactions == []
    assert not [call for call in sdk.hunts.calls if call[0] == 'interactions']

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('7')
            deadline = time.monotonic() + 1
            while not session.pending_interactions and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            await pilot.pause()
            assert [
                row['requestId'] for row in session.pending_interactions
            ] == ['approval-1']
            operator_status = str(
                app.query_one('#operator-status').render()
            ).lower()
            assert 'pending interaction' in operator_status
            assert '7 or i' in operator_status

    asyncio.run(exercise())


def test_fullscreen_app_animates_active_tab_during_network_refresh():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    original_refresh = session.refresh

    def delayed_refresh(view=None, **kwargs):
        time.sleep(0.25)
        return original_refresh(view, **kwargs)

    session.refresh = delayed_refresh

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)):
            session.select_view('vulnerabilities')
            refresh = asyncio.create_task(app._refresh_active())
            await asyncio.sleep(0.03)

            tab = app.query_one('#view-vulnerabilities')
            assert str(tab.label).startswith('2 Vulnerabilities ⠋')
            assert 'Loading Vulnerabilities' in str(
                app.query_one('#operator-status').render()
            )

            app._advance_loading_spinner()
            assert str(tab.label).startswith('2 Vulnerabilities ⠙')
            await refresh
            assert str(tab.label) == '2 Vulnerabilities'

    asyncio.run(exercise())


def test_manual_refresh_blocks_input_with_centered_grey_spinner_modal():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    original_refresh = session.refresh
    refresh_started = threading.Event()
    allow_refresh = threading.Event()

    def delayed_refresh(view=None, **kwargs):
        refresh_started.set()
        allow_refresh.wait(timeout=2)
        return original_refresh(view, **kwargs)

    session.refresh = delayed_refresh

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(100, 20)) as pilot:
            assert len(list(app.query('#view-scroll'))) == 1
            assert 'overflow-x: hidden' in HuntOpenApp.CSS
            await pilot.press('r')
            while not refresh_started.is_set():
                await asyncio.sleep(0.005)
            modal = app.screen
            assert isinstance(modal, RefreshModal)
            message = modal.query_one('#refresh-message')
            first_frame = str(message.render())
            assert 'REFRESHING OVERVIEW' in first_frame
            assert 'align: center middle' in RefreshModal.CSS
            assert 'background: #374151 75%' in RefreshModal.CSS
            await pilot.press('2')
            assert session.active_view == 'overview'
            await asyncio.sleep(0.12)
            assert str(message.render()) != first_frame
            allow_refresh.set()
            deadline = time.monotonic() + 1
            while isinstance(app.screen, RefreshModal) and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            assert not isinstance(app.screen, RefreshModal)

    asyncio.run(exercise())


def test_conversation_navigation_shows_bottom_loading_feedback():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('chat', raise_errors=True)
    session.select_view('chat')
    original_move = session.chat_session.move_selection
    move_started = threading.Event()
    allow_move = threading.Event()

    def delayed_move(delta):
        move_started.set()
        allow_move.wait(timeout=2)
        return original_move(delta)

    session.chat_session.move_selection = delayed_move

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.press('down')
            while not move_started.is_set():
                await asyncio.sleep(0.005)
            assert 'Loading Chat' in str(
                app.query_one('#operator-status').render()
            )
            allow_move.set()
            deadline = time.monotonic() + 1
            while (
                session.chat_session.selected_id != 'child'
                and time.monotonic() < deadline
            ):
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert session.chat_session.selected_id == 'child'
            assert 'Loading Chat' not in str(
                app.query_one('#operator-status').render()
            )

    asyncio.run(exercise())


def test_tab_change_during_slow_refresh_runs_the_new_view_immediately():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    original_refresh = session.refresh

    def delayed_refresh(view=None, **kwargs):
        if view == 'vulnerabilities':
            time.sleep(0.08)
        return original_refresh(view, **kwargs)

    session.refresh = delayed_refresh

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)):
            session.select_view('vulnerabilities')
            first_refresh = app._start_active_refresh()
            await asyncio.sleep(0.02)
            app._cancel_active_refresh()
            session.select_view('memory')
            second_refresh = app._start_active_refresh()
            await second_refresh
            await asyncio.gather(first_refresh, return_exceptions=True)
            assert first_refresh.done()
            assert session.active_view == 'memory'
            assert 'memory' in session.loaded_views
            assert (
                'memory', HUNT_ID, MEMORY_REFRESH_MAX_PAGES,
            ) in sdk.hunts.calls

    asyncio.run(exercise())


def test_unified_hunt_never_refreshes_automatically():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)
    calls_before_mount = list(sdk.hunts.calls)

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)):
            await asyncio.sleep(1.1)
            assert sdk.hunts.calls == calls_before_mount

    asyncio.run(exercise())


def test_view_navigation_refresh_and_close_actions_work_from_keyboard():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.press('right')
            await pilot.pause()
            assert session.active_view == 'vulnerabilities'
            await pilot.press('left')
            await pilot.pause()
            assert session.active_view == 'overview'
            await pilot.press('3')
            await pilot.pause()
            assert session.active_view == 'workflow'
            workflow_calls = sum(
                1 for call in sdk.hunts.calls if call[0] == 'workflows'
            )
            await pilot.press('r')
            await pilot.pause()
            assert sum(
                1 for call in sdk.hunts.calls if call[0] == 'workflows'
            ) == workflow_calls + 1
            await pilot.press('q')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise()) == 'close'


def test_hunt_open_escape_returns_to_previous_screen():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('escape')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise()) == 'close'


def test_memory_new_action_works_while_hunt_is_paused():
    sdk = _sdk()
    sdk.hunts.hunt['status'] = 'paused'
    sdk.hunts.memory_items = []
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('memory', raise_errors=True)
    session.select_view('memory')

    assert 'Press n to create the first memory item' in _render(
        session.render('memory')
    )

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('n')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise()) == 'memory-new'


def test_workflow_conversation_routes_to_the_embedded_chat_tab():
    sdk = _sdk()
    sdk.hunts.workflows[0]['steps'] = [
        {'kind': 'func', 'name': 'setup', 'status': 'completed'},
        {'kind': 'agent', 'conversation_id': 'root', 'status': 'running'},
        {'kind': 'agent', 'conversation_id': 'child', 'status': 'running'},
    ]

    workflow_session = HuntOpenSession(sdk, HUNT_ID)
    workflow_session.refresh('workflow', raise_errors=True)
    workflow_session.select_view('workflow')

    async def open_workflow_chat():
        app = HuntOpenApp(workflow_session)
        async with app.run_test(size=(140, 40)) as pilot:
            # First Enter selects the workflow's child list. Up/Down then move
            # within those children; the second Enter routes to Chat.
            await pilot.press('enter')
            await pilot.pause()
            assert workflow_session.workflow_browser.step_mode is True
            assert workflow_session.workflow_browser.current_step['name'] == 'setup'
            assert workflow_session.workflow_browser.current_conversation_id == ''
            await pilot.press('down')
            await pilot.pause()
            assert (
                workflow_session.workflow_browser.current_conversation_id
                == 'root'
            )
            await pilot.press('down')
            await pilot.pause()
            assert (
                workflow_session.workflow_browser.current_conversation_id
                == 'child'
            )
            await pilot.press('enter')
            deadline = time.monotonic() + 1
            while (
                workflow_session.chat_session.selected_id != 'child'
                and time.monotonic() < deadline
            ):
                await asyncio.sleep(0.005)
            await pilot.pause()
            assert workflow_session.active_view == 'chat'
            assert workflow_session.chat_session.selected_id == 'child'
            assert app.return_value is None

    asyncio.run(open_workflow_chat())


def test_context_shortcuts_open_memory_chat_and_approvals_surfaces():
    cases = (
        ('memory', 'm', 'memory'),
        ('chat', 'c', 'chat'),
        ('approvals', 'i', 'approvals'),
    )
    for view, key, expected in cases:
        sdk = _sdk()
        session = HuntOpenSession(sdk, HUNT_ID)
        session.refresh(view, raise_errors=True)
        session.select_view(view)

        async def exercise():
            app = HuntOpenApp(session)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.press(key)
                await pilot.pause()
            return app.return_value

        assert asyncio.run(exercise()) == expected


def test_lifecycle_actions_reject_invalid_state_and_allow_valid_actions():
    sdk = _sdk()
    sdk.hunts.hunt['status'] = 'paused'
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)

    async def reject_pause_then_resume():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('p')
            await pilot.pause()
            assert 'cannot pause while paused' in session.notice
            assert app.return_value is None
            await pilot.press('u')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(reject_pause_then_resume()) == 'resume'

    async def stop_paused_hunt():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press('x')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(stop_paused_hunt()) == 'stop'


def test_fullscreen_app_exposes_seven_keyboard_tabs_and_lifecycle_outcome():
    sdk = _sdk()
    session = HuntOpenSession(sdk, HUNT_ID)
    session.refresh('overview', raise_errors=True)

    async def exercise():
        app = HuntOpenApp(session)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            assert len(app.query('Tab')) == 7
            await pilot.press('7')
            await pilot.pause()
            assert session.active_view == 'approvals'
            assert 'pending interaction' in str(
                app.query_one('#operator-status').render()
            ).lower()
            await pilot.press('p')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise()) == 'pause'
