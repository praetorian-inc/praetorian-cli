import pytest
from rich.console import Console

from praetorian_cli.sdk.test.ui_mocks import MockMenuBase
from praetorian_cli.ui.aegis import menu as menu_module
from praetorian_cli.ui.aegis.commands.hunt import complete, handle_hunt
from praetorian_cli.ui.hunt_defaults import DEFAULT_FINISH_CRITERIA
from praetorian_cli.ui.aegis.menu import AegisMenu


pytestmark = pytest.mark.tui

ENDPOINT_ID = '11111111-1111-4111-8111-111111111111'
OTHER_ENDPOINT_ID = '22222222-2222-4222-8222-222222222222'
SCOPE = '#asset#internal.example#10.0.0.5'


class V2Endpoint:
    def __init__(self, endpoint_id=ENDPOINT_ID, hostname='sensor', online=True):
        self.endpoint_id = endpoint_id
        self.hostname = hostname
        self.is_online = online
        self.version = 'v2'
        self.kind = 'aegis'

    @property
    def client_id(self):
        raise AssertionError('AI Hunts must not inspect legacy client_id')

    @property
    def display_id(self):
        return self.endpoint_id


class V1Agent:
    client_id = 'C.1'
    endpoint_id = None
    hostname = 'legacy'
    version = 'v1'
    kind = 'aegis'


class FakeAegis:
    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.calls = 0

    def list_hunt_endpoints(self):
        self.calls += 1
        return list(self.endpoints)


class FakeHunts:
    def __init__(self):
        self.create_calls = []
        self.mutation_calls = []
        self.hunts = []
        self.endpoint_status = {'sessions': [], 'tasks': []}
        self.workflow_runs = []
        self.conversations = []
        self.interactions = []
        self.interaction_calls = []
        self.findings = []
        self.memory_items = []
        self.memory_content = {}
        self.memory_calls = []
        self.log = ''

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {'uuid': 'hunt-1', 'status': 'active', **kwargs}

    def list(self, status=None, pages=1):
        hunts = self.hunts
        if status:
            hunts = [hunt for hunt in hunts if hunt.get('status') == status]
        return list(hunts), None

    def get(self, hunt_id):
        return next(
            (hunt for hunt in self.hunts if hunt.get('uuid') == hunt_id),
            None,
        )

    def endpoint_execution_status(self, _hunt):
        return self.endpoint_status

    def list_workflow_runs(self, _hunt_id):
        return list(self.workflow_runs), None

    def list_conversations(self, _hunt_id):
        return list(self.conversations), None

    def list_interactions(self, hunt_id, status='pending'):
        self.interaction_calls.append((hunt_id, status))
        return list(self.interactions)

    def list_findings(self, _hunt_id, pages=1):
        return list(self.findings), None

    def list_memory(self, _hunt_id):
        return list(self.memory_items), None

    def get_memory(self, _hunt_id, title):
        return self.memory_content[title]

    def save_memory(self, hunt_id, title, content):
        self.memory_calls.append(('save', hunt_id, title, content))

    def delete_memory(self, hunt_id, title):
        self.memory_calls.append(('delete', hunt_id, title))

    def get_log(self, _hunt_id):
        return self.log

    def pause(self, hunt_id):
        self.mutation_calls.append(('pause', hunt_id))

    def resume(self, hunt_id):
        self.mutation_calls.append(('resume', hunt_id))

    def stop(self, hunt_id):
        self.mutation_calls.append(('stop', hunt_id))

    def delete(self, hunt_id):
        self.mutation_calls.append(('delete', hunt_id))


class FakeAssets:
    def __init__(self):
        self.candidates = []

    def list_hunt_scope(self, **_kwargs):
        return list(self.candidates), None


class FakeRisks:
    def get(self, key, details=False, evidence='off'):
        return {'key': key, 'status': 'OH', 'statusLabel': 'Open High'}


class FakeCredentials:
    def __init__(self):
        self.records = []

    def list(self, pages=1):
        assert pages == 1
        return list(self.records), None


class FakeConversations:
    def __init__(self):
        self.sent = []
        self.transcripts = {}

    def send_message(self, conversation_id, message):
        self.sent.append((conversation_id, message))

    def get(self, conversation_id):
        return self.transcripts.get(conversation_id, {'messages': []})


class Menu(MockMenuBase):
    def __init__(self, selected_agent=None, authorized_endpoints=None):
        super().__init__()
        self.selected_agent = selected_agent
        self.sdk = type('SDK', (), {})()
        self.sdk.aegis = FakeAegis(
            authorized_endpoints
            if authorized_endpoints is not None
            else ([selected_agent] if selected_agent else [])
        )
        self.sdk.hunts = FakeHunts()
        self.sdk.assets = FakeAssets()
        self.sdk.risks = FakeRisks()
        self.sdk.credentials = FakeCredentials()
        self.sdk.conversations = FakeConversations()


def _hunt(endpoint_id=ENDPOINT_ID, hunt_id='hunt-1', status='active'):
    return {
        'uuid': hunt_id,
        'status': status,
        'endpointRequired': True,
        'endpointId': endpoint_id,
        'iterationCount': 2,
        'findingsCount': 3,
        'prompt': 'Assess internal services',
    }


def test_launch_uses_selected_authorized_v2_endpoint():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)

    handle_hunt(menu, [
        'launch',
        '--scope', SCOPE,
        '--prompt', 'Assess internal services',
        '--expires', '8',
        '--scope-level', 'strict',
        '--aggressiveness', 'cautious',
        '--yes',
    ])

    assert menu.sdk.aegis.calls == 1
    assert menu.sdk.hunts.create_calls == [{
        'prompt': 'Assess internal services',
        'expires_hours': 8,
        'agent': 'hannibal',
        'scope': [SCOPE],
        'scope_level': 'strict',
        'aggressiveness': 'cautious',
        'finish_criteria': DEFAULT_FINISH_CRITERIA,
        'user_guardrails': '',
        'custom_tag': '',
        'model_tier_override': None,
        'credential_ids': None,
        'endpoint_required': True,
        'endpoint_id': ENDPOINT_ID,
        'endpoint_confirmed': True,
    }]
    assert 'AI Hunt launched' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_launch_discovers_targets_and_sends_ui_configuration(monkeypatch):
    menu = Menu(V2Endpoint())
    menu.sdk.assets.candidates = [{'key': SCOPE, 'dns': 'internal.example'}]
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.select_entity_keys',
        lambda console, entities, title, **_kwargs: [entities[0]['key']],
    )

    handle_hunt(menu, [
        'launch',
        '--prompt', 'Assess internal services',
        '--finish-criteria', 'Stop after compromise',
        '--guardrails', 'Do not authenticate',
        '--custom-tag', 'Internal-Q4',
        '--model-tier', 'experimental',
        '--yes',
    ])

    call = menu.sdk.hunts.create_calls[0]
    assert call['scope'] == [SCOPE]
    assert call['expires_hours'] == 24
    assert call['finish_criteria'] == 'Stop after compromise'
    assert call['user_guardrails'] == 'Do not authenticate'
    assert call['custom_tag'] == 'Internal-Q4'
    assert call['model_tier_override'] == 'experimental'


def test_interactive_launch_wizard_updates_configuration(monkeypatch):
    menu = Menu(V2Endpoint())
    menu.sdk.credentials.records = [
        {
            'credentialId': 'ad-1',
            'type': 'active-directory',
            'name': 'Corp AD',
            'endpointIds': [ENDPOINT_ID],
        },
        {
            'credentialId': 'ad-other',
            'type': 'active-directory',
            'endpointIds': [OTHER_ENDPOINT_ID],
        },
        {
            'credentialId': 'web-1',
            'type': 'web-auth',
            'accountKey': '#webapplication#https://internal.example/',
        },
    ]
    configured = {
        'prompt': 'Prioritize domain controllers',
        'aggressiveness': 'aggressive',
        'guardrails': 'Do not test authentication',
        'finish_criteria': 'Stop after one critical finding',
        'expires': 48,
        'custom_tag': 'Internal-Q4',
        'model_tier': 'experimental',
        'credential_ids': ['ad-1', 'web-1'],
    }
    available_credentials = []

    def configure(*args, **_kwargs):
        available_credentials.extend(args[4])
        return configured, True

    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.configure_hunt_launch',
        configure,
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.Confirm.ask',
        lambda *_args, **_kwargs: pytest.fail(
            'the fullscreen wizard owns launch confirmation'
        ),
    )

    handle_hunt(menu, [
        'launch', '--scope', SCOPE, '--prompt', 'Initial objective',
    ])

    call = menu.sdk.hunts.create_calls[0]
    assert call['prompt'] == 'Prioritize domain controllers'
    assert call['aggressiveness'] == 'aggressive'
    assert call['user_guardrails'] == 'Do not test authentication'
    assert call['finish_criteria'] == 'Stop after one critical finding'
    assert call['expires_hours'] == 48
    assert call['custom_tag'] == 'Internal-Q4'
    assert call['model_tier_override'] == 'experimental'
    assert call['credential_ids'] == ['ad-1', 'web-1']
    assert [
        credential['credentialId'] for credential in available_credentials
    ] == ['ad-1', 'web-1']


def test_subcommand_help_does_not_require_selected_endpoint():
    menu = Menu()

    handle_hunt(menu, ['launch', '--help'])

    assert 'Aegis v2 AI Hunt Commands' in '\n'.join(menu.console.lines)
    assert menu.sdk.aegis.calls == 0


@pytest.mark.parametrize('selected_agent', [None, V1Agent()])
def test_hunt_requires_selected_v2_endpoint(selected_agent):
    menu = Menu(selected_agent)

    handle_hunt(menu, [
        'launch', '--scope', SCOPE, '--prompt', 'Assess', '--yes',
    ])

    assert menu.sdk.hunts.create_calls == []
    assert menu.paused is True


def test_launch_revalidates_selected_endpoint_authorization():
    menu = Menu(V2Endpoint(), authorized_endpoints=[V2Endpoint(OTHER_ENDPOINT_ID)])

    handle_hunt(menu, [
        'launch', '--scope', SCOPE, '--prompt', 'Assess', '--yes',
    ])

    assert menu.sdk.hunts.create_calls == []
    assert 'no longer authorized' in '\n'.join(menu.console.lines)


def test_launch_confirmation_names_offline_waiting_policy(monkeypatch):
    endpoint = V2Endpoint(online=False)
    menu = Menu(endpoint)
    prompts = []
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.Confirm.ask',
        lambda message, default: prompts.append((message, default)) or False,
    )

    handle_hunt(menu, [
        'launch', '--scope', SCOPE, '--prompt', 'Assess',
    ])

    assert menu.sdk.hunts.create_calls == []
    assert 'offline' in prompts[0][0]
    assert 'waits without external compute fallback' in prompts[0][0]
    assert prompts[0][1] is False


def test_list_filters_hunts_to_selected_endpoint():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [
        _hunt(),
        _hunt(OTHER_ENDPOINT_ID, 'hunt-2'),
        {'uuid': 'hunt-3', 'status': 'active'},
    ]

    handle_hunt(menu, ['list'])

    output = menu.console.export_text()
    assert 'hunt-1' in output
    assert 'hunt-2' not in output
    assert 'hunt-3' not in output


def test_status_renders_endpoint_execution_state_and_workflows():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [_hunt()]
    menu.sdk.hunts.workflow_runs = [{
        'run_id': 'run-1',
        'definition': 'hunt',
        'status': 'running',
        'created': '2026-01-01T02:00:00Z',
        'steps': [{
            'name': 'target-selection',
            'title': 'Target Selection',
            'kind': 'agent',
            'status': 'running',
        }],
    }]
    menu.sdk.hunts.endpoint_status = {
        'sessions': [],
        'tasks': [{
            'endpointId': ENDPOINT_ID,
            'taskId': 'task-1',
            'jobKey': '#job#1',
            'capability': 'portscan',
            'target': SCOPE,
            'state': 'Ready',
            'phase': 'waiting_for_endpoint',
            'endpointConnectionState': 'not_connected',
        }],
    }

    handle_hunt(menu, ['status', 'hunt-1', '--workflows'])

    output = menu.console.export_text()
    assert 'AI Hunt hunt-1' in output
    assert 'Waiting for assigned endpoint (no compute fallback)' in output
    assert 'Iteration 1' in output
    assert 'Target Selection' in output
    assert 'AGENT' in output
    assert 'RUNNING' in output


def test_status_workflow_step_opens_exact_live_conversation(monkeypatch):
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.sdk.hunts.hunts = [_hunt()]
    menu.sdk.hunts.workflow_runs = [{
        'run_id': 'run-1',
        'steps': [{
            'name': 'dispatch-agent',
            'conversation_id': 'conversation-exact',
        }],
    }]
    calls = []

    def open_selected(_console, runs, *, open_conversation):
        assert runs == menu.sdk.hunts.workflow_runs
        open_conversation(runs[0]['steps'][0]['conversation_id'])

    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.browse_hunt_workflows',
        open_selected,
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.run_live_hunt_chat',
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    handle_hunt(menu, ['status', 'hunt-1', '--workflows'])

    assert calls[0][0] == (menu.sdk, 'hunt-1')
    assert calls[0][1]['requested_id'] == 'conversation-exact'
    assert calls[0][1]['exact_requested_id'] is True
    assert callable(calls[0][1]['review_interactions'])


def test_findings_memory_and_log_commands_render_hunt_data():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [_hunt()]
    menu.sdk.hunts.findings = [{
        'key': '#risk#db#sql',
        'dns': 'db.example',
        'title': 'SQL injection',
        'status': 'OH',
        'statusLabel': 'Open High',
    }]
    menu.sdk.hunts.memory_items = [{
        'title': 'target.md',
        'bytes': 10,
        'updated': '2026-01-01T00:00:00Z',
    }]
    menu.sdk.hunts.memory_content['target.md'] = 'remember this target'
    menu.sdk.hunts.log = '[iteration-complete] confirmed SMB'

    handle_hunt(menu, ['findings', 'hunt-1', '--severity', 'high'])
    handle_hunt(menu, ['memory', 'hunt-1'])
    handle_hunt(menu, ['memory', 'hunt-1', '--item', 'target.md'])
    handle_hunt(menu, [
        'memory', 'hunt-1', '--item', 'target.md', '--content', 'updated',
    ])
    handle_hunt(menu, [
        'memory', 'hunt-1', '--item', 'target.md', '--delete', '--yes',
    ])
    handle_hunt(menu, ['log', 'hunt-1'])

    output = menu.console.export_text()
    assert 'SQL injection' in output
    assert 'target.md' in output
    assert 'remember this target' in output
    assert 'confirmed SMB' in output
    assert menu.sdk.hunts.memory_calls == [
        ('save', 'hunt-1', 'target.md', 'updated'),
        ('delete', 'hunt-1', 'target.md'),
    ]


def test_chat_opens_fullscreen_live_view_without_menu_pause(monkeypatch):
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.sdk.hunts.hunts = [_hunt()]
    calls = []
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.supports_live_hunt_chat',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.hunt.run_live_hunt_chat',
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    handle_hunt(menu, [
        'chat', 'hunt-1', '--conversation', 'root-prefix', '--interval', '2',
    ])

    assert calls[0][0] == (menu.sdk, 'hunt-1')
    assert calls[0][1]['requested_id'] == 'root-prefix'
    assert calls[0][1]['refresh_interval'] == 2.0
    assert callable(calls[0][1]['review_interactions'])
    assert menu.paused is False


def test_chat_displays_transcript_and_queues_guidance():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [_hunt()]
    menu.sdk.hunts.conversations = [{
        'uuid': 'conversation-1',
        'status': 'active',
        'parent_id': 'self',
        'created': '2026-01-01T02:00:00Z',
    }]
    menu.sdk.conversations.transcripts['conversation-1'] = {
        'messages': [{
            'role': 'chariot',
            'content': 'Testing the selected target.',
            'timestamp': '2026-01-01T02:01:00Z',
        }],
    }

    handle_hunt(menu, [
        'chat',
        'hunt-1',
        '--message',
        'Focus on SMB',
    ])

    output = menu.console.export_text()
    assert menu.sdk.conversations.sent == [
        ('conversation-1', 'Focus on SMB')
    ]
    assert 'Hannibal Hunt Chat' in output
    assert 'Testing the selected target.' in output
    assert 'Guidance queued' in output


def test_interactions_are_hunt_scoped_and_limited_to_selected_endpoint():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [
        _hunt(),
        _hunt(OTHER_ENDPOINT_ID, 'hunt-2'),
    ]
    menu.sdk.hunts.interactions = [{
        'conversationId': 'child-conversation',
        'requestId': 'request-1',
        'kind': 'credential',
        'status': 'pending',
        'request': 'MODEL TEXT WITH VALUE-THAT-MUST-NOT-RENDER',
        'fields': ['username', 'password'],
    }]

    handle_hunt(menu, ['interactions', 'hunt-1'])
    handle_hunt(menu, ['interactions', 'hunt-2'])

    output = menu.console.export_text()
    assert menu.sdk.hunts.interaction_calls == [('hunt-1', 'pending')]
    assert 'Pending Hunt interactions' in output
    assert 'username, password' in output
    assert 'VALUE-THAT-MUST-NOT-RENDER' not in output
    assert 'does not belong to the selected endpoint' in output


def test_lifecycle_mutations_are_limited_to_selected_endpoint():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.sdk.hunts.hunts = [
        _hunt(),
        _hunt(OTHER_ENDPOINT_ID, 'hunt-2'),
    ]

    handle_hunt(menu, ['pause', 'hunt-1'])
    handle_hunt(menu, ['stop', 'hunt-1', '--yes'])
    handle_hunt(menu, ['delete', 'hunt-2', '--yes'])

    assert menu.sdk.hunts.mutation_calls == [
        ('pause', 'hunt-1'),
        ('stop', 'hunt-1'),
    ]
    assert 'does not belong to the selected endpoint' in '\n'.join(
        menu.console.lines
    )


def test_aegis_menu_registers_and_dispatches_hunt(monkeypatch):
    sdk = type('SDK', (), {
        'get_current_user': lambda _self: ('user@example.com', 'user'),
    })()
    menu = AegisMenu(sdk)
    calls = []
    monkeypatch.setattr(
        menu_module,
        'cmd_handle_hunt',
        lambda received_menu, args: calls.append((received_menu, args)),
    )

    result = menu.handle_choice('hunt status hunt-1')

    assert 'hunt' in menu.commands
    assert result is True
    assert calls == [(menu, ['status', 'hunt-1'])]


def test_hunt_completion_lists_subcommands_and_options():
    menu = Menu(V2Endpoint())

    assert complete(menu, 'la', ['hunt', 'la']) == ['launch']
    assert '--scope' in complete(menu, '--', ['hunt', 'launch', '--'])
    assert '--credential' in complete(menu, '--', ['hunt', 'launch', '--'])
    assert complete(menu, '--s', ['hunt', 'list', '--s']) == ['--status']
    assert complete(
        menu,
        '--w',
        ['hunt', 'status', 'hunt-1', '--w'],
    ) == ['--workflows']
    assert complete(
        menu,
        '--m',
        ['hunt', 'chat', 'hunt-1', '--m'],
    ) == ['--message']
    assert complete(
        menu,
        '--w',
        ['hunt', 'interactions', 'hunt-1', '--w'],
    ) == ['--watch']
    assert complete(
        menu,
        '--sev',
        ['hunt', 'findings', 'hunt-1', '--sev'],
    ) == ['--severity']
    assert complete(
        menu,
        '--f',
        ['hunt', 'log', 'hunt-1', '--f'],
    ) == ['--follow']
