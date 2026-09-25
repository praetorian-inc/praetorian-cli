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


def _credential():
    return {
        'conversationId': 'conversation-1',
        'requestId': 'credential-1',
        'kind': 'credential',
        'status': 'pending',
        'request': 'UNTRUSTED MODEL TEXT',
        'fields': ['username', 'password'],
    }


class FakeConversations:
    def __init__(self, interactions):
        self.interactions = interactions
        self.answers = []
        self.stops = []
        self.guidance = []
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

    def stop(self, conversation_id):
        self.stops.append(conversation_id)
        return {'status': 'stopping'}

    def send_message(self, conversation_id, message):
        self.guidance.append((conversation_id, message))
        return {'status': 'queued'}

    def tree_ids(self, conversation_id):
        assert conversation_id == 'conversation-1'
        return [
            'conversation-1',
            '22222222-2222-4222-8222-222222222222',
        ]

    def get_metadata(self, conversation_id):
        return {
            'uuid': conversation_id,
            'status': 'active',
            'topic': (
                'Marcus root'
                if conversation_id == 'conversation-1'
                else 'Subagent: hitl-romulus-agent'
            ),
        }


class FakeCredentials:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add_ephemeral(self, parameters):
        self.added.append(dict(parameters))
        return {'credentialValue': {'credential_id': 'opaque-reference'}}

    def delete_ephemeral(self, credential_id):
        self.deleted.append(credential_id)


class FakeEndpointExecutions:
    def __init__(self):
        self.status = {'sessions': [], 'tasks': []}

    def conversation_status(self, _conversation_id):
        return self.status


class FakeSDK:
    def __init__(self, interactions):
        self.conversations = FakeConversations(interactions)
        self.credentials = FakeCredentials()
        self.endpoint_executions = FakeEndpointExecutions()

    def get_current_user(self):
        return 'user@example.com', 'user'


def test_agent_ask_wires_approval_and_credential_interactions(monkeypatch):
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
            ('approval', received_sdk, interaction['requestId'])
        ),
    )
    monkeypatch.setattr(
        agent_handler,
        'prompt_ephemeral_credentials',
        lambda received_sdk, interaction, **_kwargs: prompted.append(
            ('credential', received_sdk, interaction['requestId'])
        ),
    )

    result = agent_handler._ask_with_interactions(sdk, 'test')

    assert result == {'response': 'done'}
    assert prompted == [
        ('credential', sdk, 'credential-1'),
        ('approval', sdk, 'request-1'),
    ]


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


def test_console_prompts_each_pending_interaction_once(monkeypatch):
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
            ('approval', received_sdk, interaction['requestId'])
        ),
    )
    monkeypatch.setattr(
        marcus_module,
        'prompt_ephemeral_credentials',
        lambda received_sdk, interaction, **_kwargs: prompted.append(
            ('credential', received_sdk, interaction['requestId'])
        ),
    )
    handled = set()

    command._handle_pending_interactions(handled)
    command._handle_pending_interactions(handled)

    assert prompted == [
        ('credential', sdk, 'credential-1'),
        ('approval', sdk, 'request-1'),
    ]
    assert handled == {'credential-1', 'request-1'}


def test_console_retries_approval_after_prompt_failure(monkeypatch):
    sdk = FakeSDK([_approval()])
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    output = []
    command.console = SimpleNamespace(
        print=lambda message='', **_kwargs: output.append(message)
    )
    attempts = []

    def prompt(*_args, **_kwargs):
        attempts.append('approval')
        if len(attempts) == 1:
            raise RuntimeError('temporary failure')

    monkeypatch.setattr(marcus_module, 'prompt_endpoint_approval', prompt)
    handled = set()

    command._handle_pending_interactions(handled)
    assert handled == set()
    assert output[-1] == 'Operator interaction failed: temporary failure'

    command._handle_pending_interactions(handled)
    assert attempts == ['approval', 'approval']
    assert handled == {'request-1'}


def test_console_retries_credentials_after_prompt_failure(monkeypatch):
    sdk = FakeSDK([_credential()])
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    command.console = SimpleNamespace(print=lambda *_args, **_kwargs: None)
    attempts = []

    def prompt(*_args, **_kwargs):
        attempts.append('credential')
        if len(attempts) == 1:
            raise RuntimeError('temporary failure')

    monkeypatch.setattr(marcus_module, 'prompt_ephemeral_credentials', prompt)
    handled = set()

    command._handle_pending_interactions(handled)
    assert handled == set()

    command._handle_pending_interactions(handled)
    assert attempts == ['credential', 'credential']
    assert handled == {'credential-1'}


def test_textual_chat_surfaces_and_allows_complete_approval():
    sdk = FakeSDK([_approval()])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    messages = []
    statuses = []
    app.add_system_message = messages.append
    app.update_status = statuses.append

    asyncio.run(app.check_for_pending_interaction())

    assert app._pending_approval['requestId'] == 'request-1'
    assert 'Aegis endpoint approval required' in messages[-1]
    assert 'UNTRUSTED MODEL TEXT' not in messages[-1]
    assert statuses[-1] == 'Endpoint approval required'

    asyncio.run(app.answer_pending_approval('allow'))

    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'true')]
    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 allowed.'


def test_textual_conversation_escape_returns_to_previous_screen():
    async def exercise():
        app = ConversationApp(FakeSDK([]), mode='agent')
        async with app.run_test() as pilot:
            await pilot.press('escape')
            await pilot.pause()
        return app.return_value

    assert asyncio.run(exercise()) == 'back'


def test_textual_chat_collects_credentials_and_sends_only_opaque_reference():
    sdk = FakeSDK([_credential()])
    app = ConversationApp(sdk, mode='agent')
    app.conversation_id = 'conversation-1'
    messages = []
    statuses = []
    app.add_system_message = messages.append
    app.update_status = statuses.append

    asyncio.run(app.check_for_pending_interaction())

    assert app._pending_credential['requestId'] == 'credential-1'
    assert 'username, password' in messages[-1]
    assert 'UNTRUSTED MODEL TEXT' not in messages[-1]
    assert statuses[-1] == 'Credential input required'

    asyncio.run(app.answer_pending_credential('VALUE-1'))
    asyncio.run(app.answer_pending_credential('VALUE-2'))

    assert sdk.credentials.added == [{
        'username': 'VALUE-1',
        'password': 'VALUE-2',
    }]
    assert sdk.conversations.answers == [(
        'conversation-1',
        'credential-1',
        'opaque-reference',
    )]
    assert app._pending_credential is None
    assert 'VALUE-1' not in '\n'.join(messages)
    assert 'VALUE-2' not in '\n'.join(messages)


def test_textual_chat_masks_each_credential_field_in_the_live_input():
    async def exercise():
        sdk = FakeSDK([_credential()])
        app = ConversationApp(sdk, mode='agent')
        async with app.run_test() as pilot:
            app.conversation_id = 'conversation-1'
            await app.check_for_pending_interaction(force=True)
            input_widget = app.query_one('#message-input')

            assert input_widget.password is True
            assert input_widget.placeholder == 'Enter username securely'

            input_widget.value = 'VALUE-1'
            await pilot.press('enter')
            await pilot.pause()
            assert input_widget.password is True
            assert input_widget.placeholder == 'Enter password securely'

            input_widget.value = 'VALUE-2'
            await pilot.press('enter')
            await pilot.pause()
            assert input_widget.password is False
            assert sdk.conversations.answers == [(
                'conversation-1',
                'credential-1',
                'opaque-reference',
            )]

    asyncio.run(exercise())


def test_textual_chat_names_agentic_steps_without_rendering_tool_inputs():
    app = ConversationApp(FakeSDK([]), mode='agent')

    label = app._tool_call_name({
        'toolUseContent': '{"Name":"spawn_agent","Input":'
        '{"agent":"hitl-romulus-agent","task":"SECRET MISSION"}}',
    })

    assert label == 'spawn_agent(hitl-romulus-agent)'
    assert 'SECRET MISSION' not in label


def test_textual_chat_focuses_a_subagent_for_live_progress_and_guidance():
    async def exercise():
        sdk = FakeSDK([])
        app = ConversationApp(sdk, mode='agent')
        app.conversation_id = 'conversation-1'
        app.root_conversation_id = 'conversation-1'
        events = []

        async def clear_chat():
            events.append('clear')

        async def load_history():
            events.append(('load', app.conversation_id))

        app.clear_chat = clear_chat
        app.load_conversation_history = load_history
        app.update_status = events.append

        await app.focus_agent('/focus 22222222')

        assert app.conversation_id == (
            '22222222-2222-4222-8222-222222222222'
        )
        assert app.root_conversation_id == 'conversation-1'
        assert events == [
            'clear',
            ('load', '22222222-2222-4222-8222-222222222222'),
            'Focused agent - Ready',
        ]

    asyncio.run(exercise())


def test_textual_chat_lists_and_steers_specific_agent_branches():
    sdk = FakeSDK([])
    app = ConversationApp(sdk, mode='agent')
    app.conversation_id = 'conversation-1'
    app.root_conversation_id = 'conversation-1'
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.show_agent_tree())
    asyncio.run(app.guide_agent('/guide 22222222 Focus on the login flow'))
    asyncio.run(app.stop_current_agent('22222222'))

    assert 'Subagent: hitl-romulus-agent' in messages[0]
    assert sdk.conversations.guidance == [(
        '22222222-2222-4222-8222-222222222222',
        'Focus on the login flow',
    )]
    assert sdk.conversations.stops == [
        '22222222-2222-4222-8222-222222222222'
    ]
    assert messages[-1] == (
        'Stop requested for agent 22222222-222 and child work'
    )


def test_textual_chat_stop_controls_marcus_and_child_work():
    sdk = FakeSDK([])
    app = ConversationApp(sdk, mode='agent')
    app.conversation_id = 'conversation-1'
    app.root_conversation_id = 'conversation-1'
    messages = []
    statuses = []
    app.add_system_message = messages.append
    app.update_status = statuses.append

    asyncio.run(app.stop_current_agent())

    assert sdk.conversations.stops == ['conversation-1']
    assert messages[-1] == 'Stop requested for Marcus and child work'
    assert statuses[-1] == 'Stopping agent...'


def test_textual_chat_never_allows_incomplete_approval():
    sdk = FakeSDK([_approval(context=False)])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.check_for_pending_interaction())
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


def test_console_endpoint_status_allows_missing_status_keys():
    sdk = FakeSDK([])
    sdk.endpoint_executions.status = {'sessions': []}
    command = object.__new__(MarcusCommands)
    command.sdk = sdk
    command.context = SimpleNamespace(conversation_id='conversation-1')
    command.console = SimpleNamespace(print=lambda *_args, **_kwargs: None)

    fingerprint = command._show_endpoint_status(None)

    assert fingerprint is not None


def test_textual_chat_clears_approval_resolved_elsewhere():
    terminal = {**_approval(), 'status': 'expired'}
    sdk = FakeSDK([terminal])
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    app._pending_approval = _approval()
    app._pending_approval_context = object()
    app._shown_interaction_ids.add('request-1')
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.check_for_pending_interaction(force=True))

    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 resolved elsewhere.'


def test_stale_approval_completion_does_not_clear_new_pending_approval():
    sdk = FakeSDK([])
    app = ConversationApp(sdk)
    old = _approval()
    current = {**_approval(), 'requestId': 'request-2'}
    app._pending_approval = current
    app._pending_approval_context = object()
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app._finish_pending_approval(old, 'allowed'))

    assert app._pending_approval is current
    assert messages == []


def test_textual_chat_handles_answer_race_without_reopening_approval():
    terminal = {**_approval(), 'status': 'answered'}
    sdk = FakeSDK([terminal])
    sdk.conversations.answer_error = RuntimeError('[409] already answered')
    app = ConversationApp(sdk)
    app.conversation_id = 'conversation-1'
    app._pending_approval = _approval()
    app._pending_approval_context = object()
    app._shown_interaction_ids.add('request-1')
    messages = []
    app.add_system_message = messages.append
    app.update_status = lambda _status: None

    asyncio.run(app.answer_pending_approval('deny'))

    assert app._pending_approval is None
    assert messages[-1] == 'Endpoint approval request-1 resolved elsewhere.'
