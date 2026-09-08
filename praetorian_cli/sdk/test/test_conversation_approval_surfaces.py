import asyncio
from types import SimpleNamespace

from praetorian_cli.handlers import agent as agent_handler
from praetorian_cli.handlers import run as run_handler
from praetorian_cli.ui.console.commands import marcus as marcus_module
from praetorian_cli.ui.console.commands.marcus import MarcusCommands
from praetorian_cli.ui.conversation.textual_chat import ConversationApp


def _approval(context=True):
    interaction = {
        'conversationId': 'conversation-1',
        'requestId': 'request-1',
        'kind': 'approval',
        'status': 'pending',
        'request': 'UNTRUSTED MODEL TEXT',
    }
    if context:
        interaction['approvalContext'] = {
            'action': 'Start endpoint session',
            'target': {
                'displayName': 'internal.example',
                'identifier': '#asset#internal.example#10.0.0.5',
            },
            'endpoint': {
                'displayName': 'sensor-1',
                'endpointId': '11111111-1111-4111-8111-111111111111',
            },
            'capabilityFamilies': [],
            'toolFamilies': ['command'],
            'expectedInternalReach': '10.0.0.0/24',
            'sessionLifetime': '1 hour',
            'impactClass': 'active, non-destructive',
            'auditIdentifiers': {
                'endpointSessionId': '22222222-2222-4222-8222-222222222222',
            },
        }
    return interaction


class FakeConversations:
    def __init__(self, interactions):
        self.interactions = interactions
        self.answers = []
        self.answer_error = None

    def list_interactions(
        self, conversation_id, status=None, include_descendants=False
    ):
        assert conversation_id == 'conversation-1'
        assert status in (None, 'pending')
        if status == 'pending':
            assert include_descendants is True
        return list(self.interactions)

    def answer_interaction(self, conversation_id, request_id, response):
        self.answers.append((conversation_id, request_id, response))
        if self.answer_error:
            raise self.answer_error
        return {'status': 'answered'}


class FakeEndpointExecutions:
    def __init__(self):
        self.status = {'sessions': [], 'tasks': []}

    def conversation_status(self, _conversation_id):
        return self.status


class FakeSDK:
    def __init__(self, interactions):
        self.conversations = FakeConversations(interactions)
        self.endpoint_executions = FakeEndpointExecutions()

    def get_current_user(self):
        return 'user@example.com', 'user'


def test_agent_ask_wires_only_approval_interactions(monkeypatch):
    prompted = []

    class FakeAgents:
        def ask(self, *args, interaction_handler=None, **kwargs):
            interaction_handler({
                'requestId': 'credential-1',
                'kind': 'credential',
            })
            interaction_handler(_approval())
            return {'response': 'done'}

    sdk = SimpleNamespace(agents=FakeAgents())
    monkeypatch.setattr(
        agent_handler,
        'prompt_endpoint_approval',
        lambda received_sdk, interaction, **_kwargs: prompted.append(
            (received_sdk, interaction['requestId'])
        ),
    )

    result = agent_handler._ask_with_approvals(sdk, 'test')

    assert result == {'response': 'done'}
    assert prompted == [(sdk, 'request-1')]


def test_run_via_agent_wires_endpoint_approvals(monkeypatch):
    prompted = []

    class FakeAgents:
        def ask(self, *args, interaction_handler=None, **kwargs):
            interaction_handler(_approval())
            return {'response': 'done'}

    sdk = SimpleNamespace(agents=FakeAgents())
    monkeypatch.setattr(
        agent_handler,
        'prompt_endpoint_approval',
        lambda received_sdk, interaction, **_kwargs: prompted.append(
            (received_sdk, interaction['requestId'])
        ),
    )

    run_handler._run_via_agent(
        sdk,
        {'capability': 'portscan'},
        '#asset#example#192.0.2.1',
    )

    assert prompted == [(sdk, 'request-1')]


def test_console_prompts_each_pending_approval_once(monkeypatch):
    sdk = FakeSDK([
        {'requestId': 'credential-1', 'kind': 'credential', 'status': 'pending'},
        _approval(),
    ])
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    command.console = SimpleNamespace(print=lambda *_args, **_kwargs: None)
    prompted = []
    monkeypatch.setattr(
        marcus_module,
        'prompt_endpoint_approval',
        lambda received_sdk, interaction, **_kwargs: prompted.append(
            (received_sdk, interaction['requestId'])
        ),
    )
    handled = set()

    command._handle_pending_approvals(handled)
    command._handle_pending_approvals(handled)

    assert prompted == [(sdk, 'request-1')]
    assert handled == {'request-1'}


def test_console_reports_approval_errors_without_aborting(monkeypatch):
    sdk = FakeSDK([_approval()])
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    output = []
    command.console = SimpleNamespace(
        print=lambda message='', **_kwargs: output.append(message)
    )
    monkeypatch.setattr(
        marcus_module,
        'prompt_endpoint_approval',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError('temporary failure')
        ),
    )

    command._handle_pending_approvals(set())

    assert output[-1] == 'Endpoint approval failed: temporary failure'


def test_textual_chat_surfaces_and_allows_complete_approval():
    sdk = FakeSDK([_approval()])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    messages = []
    statuses = []
    app.add_system_message = messages.append
    app.update_status = statuses.append

    asyncio.run(app.check_for_pending_approval())

    assert app._pending_approval['requestId'] == 'request-1'
    assert 'Aegis endpoint approval required' in messages[-1]
    assert 'UNTRUSTED MODEL TEXT' not in messages[-1]
    assert statuses[-1] == 'Endpoint approval required'

    asyncio.run(app.answer_pending_approval('allow'))

    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'true')]
    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 allowed.'


def test_textual_chat_never_allows_incomplete_approval():
    sdk = FakeSDK([_approval(context=False)])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.check_for_pending_approval())
    asyncio.run(app.answer_pending_approval('allow'))

    assert sdk.conversations.answers == []
    assert 'cannot be allowed' in messages[-1]

    asyncio.run(app.answer_pending_approval('deny'))

    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'false')]


def test_textual_chat_renders_endpoint_status_without_output_tails():
    sdk = FakeSDK([])
    sdk.endpoint_executions.status = {
        'sessions': [{
            'sessionId': 'session-1',
            'endpointId': 'endpoint-1',
            'taskId': 'bootstrap-1',
            'state': 'Ready',
            'phase': 'executing_tool',
            'connection': {'state': 'connected'},
            'sandbox': {'health': 'healthy'},
            'operationCount': 1,
            'activeOperationCount': 1,
            'activeOperations': [{
                'operationId': 'operation-1',
                'tool': 'command',
                'state': 'Running',
                'stdout': 'SECRET_OUTPUT',
            }],
        }],
        'tasks': [],
    }
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    messages = []
    app.add_system_message = messages.append

    asyncio.run(app.check_endpoint_status())
    asyncio.run(app.check_endpoint_status(force=True))

    assert len(messages) == 1
    assert 'Executing endpoint tool' in messages[0]
    assert 'SECRET_OUTPUT' not in messages[0]


def test_console_renders_only_changed_endpoint_status():
    sdk = FakeSDK([])
    sdk.endpoint_executions.status = {
        'sessions': [],
        'tasks': [{
            'endpointId': 'endpoint-1',
            'taskId': 'task-1',
            'jobKey': '#job#1',
            'capability': 'portscan',
            'target': '#asset#internal#10.0.0.5',
            'state': 'Claimed',
            'phase': 'running',
            'endpointConnectionState': 'online',
        }],
    }
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    output = []
    command.console = SimpleNamespace(
        print=lambda *args, **_kwargs: output.append(args)
    )

    fingerprint = command._show_endpoint_status(None)
    command._show_endpoint_status(fingerprint)

    rendered = '\n'.join(str(value) for call in output for value in call)
    assert 'Running on endpoint' in rendered
    assert rendered.count('Running on endpoint') == 1


def test_textual_chat_clears_approval_resolved_elsewhere():
    terminal = {**_approval(), 'status': 'expired'}
    sdk = FakeSDK([terminal])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    app._pending_approval = _approval()
    app._pending_approval_context = object()
    app._shown_approval_ids.add('request-1')
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.check_for_pending_approval(force=True))

    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 resolved elsewhere.'


def test_textual_chat_handles_answer_race_without_reopening_approval():
    terminal = {**_approval(), 'status': 'answered'}
    sdk = FakeSDK([terminal])
    sdk.conversations.answer_error = RuntimeError('[409] already answered')
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    app._pending_approval = _approval()
    app._pending_approval_context = object()
    app._shown_approval_ids.add('request-1')
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.answer_pending_approval('deny'))

    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 resolved elsewhere.'
