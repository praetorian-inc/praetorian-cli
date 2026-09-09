import pytest
from rich.console import Console

from praetorian_cli.sdk.test.ui_mocks import MockMenuBase
from praetorian_cli.ui.aegis import menu as menu_module
from praetorian_cli.ui.aegis.commands.hunt import complete, handle_hunt
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

    def pause(self, hunt_id):
        self.mutation_calls.append(('pause', hunt_id))

    def resume(self, hunt_id):
        self.mutation_calls.append(('resume', hunt_id))

    def stop(self, hunt_id):
        self.mutation_calls.append(('stop', hunt_id))

    def delete(self, hunt_id):
        self.mutation_calls.append(('delete', hunt_id))


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
        'endpoint_required': True,
        'endpoint_id': ENDPOINT_ID,
        'endpoint_confirmed': True,
    }]
    assert 'AI Hunt launched' in '\n'.join(menu.console.lines)
    assert menu.paused is True


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


def test_status_renders_endpoint_execution_state():
    endpoint = V2Endpoint()
    menu = Menu(endpoint)
    menu.console = Console(record=True, force_terminal=False, width=120)
    menu.sdk.hunts.hunts = [_hunt()]
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

    handle_hunt(menu, ['status', 'hunt-1'])

    output = menu.console.export_text()
    assert 'AI Hunt hunt-1' in output
    assert 'Waiting for assigned endpoint (no compute fallback)' in output


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
    assert complete(menu, '--s', ['hunt', 'list', '--s']) == ['--status']
