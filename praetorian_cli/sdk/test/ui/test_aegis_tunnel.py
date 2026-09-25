import pytest

from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK
from praetorian_cli.ui.aegis.commands.tunnel import complete, handle_tunnel

pytestmark = pytest.mark.tui


class V2Endpoint:
    hostname = 'sensor'
    endpoint_id = 'endpoint-1'
    version = 'v2'

    @property
    def client_id(self):
        raise AssertionError('v2 tunnel commands must not inspect legacy client_id')

    @property
    def has_tunnel(self):
        raise AssertionError('v2 tunnel commands must not inspect legacy tunnel state')

    @property
    def health_check(self):
        raise AssertionError('v2 tunnel commands must not inspect legacy tunnel state')


class V1Agent:
    hostname = 'agent'
    client_id = 'C.1'
    endpoint_id = None
    version = 'v1'


class Menu(MockMenuBase):
    def __init__(self, selected_agent=None):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = selected_agent


def test_tunnel_status_prints_v2_configuration_and_runtime_diagnostics():
    status = {
        'configuration': {
            'state': 'configured',
            'hostname': 'sensor.example.com',
            'tunnelName': 'sensor-tunnel',
        },
        'runtime': {
            'state': 'running',
            'reason': 'no_edge',
            'detail': 'connector has no ready connections',
            'observedAt': '2026-09-17T12:00:00Z',
            'authorizedUsers': ['operator-one', 'operator-two'],
            'service': {
                'loadState': 'loaded',
                'activeState': 'active',
                'subState': 'running',
                'result': 'success',
                'exitCode': '0',
                'exitStatus': '0',
            },
            'connector': {
                'state': 'not_ready',
                'readyConnections': 0,
                'detail': 'no ready connections',
            },
            'origin': {'state': 'up'},
            'lastError': {
                'observedAt': '2026-09-17T11:59:00Z',
                'message': 'connection refused',
            },
            'networkLogs': [{
                'observedAt': '2026-09-17T11:58:00Z',
                'kind': 'tls',
                'message': 'certificate rejected',
            }],
        },
    }
    menu = Menu(V2Endpoint())
    menu.sdk = MockSDK({'tunnel_status': status})

    handle_tunnel(menu, ['status'])

    assert menu.sdk.aegis.calls == [{
        'method': 'get_cloudflare_tunnel_status',
        'endpoint_id': 'endpoint-1',
    }]
    output = '\n'.join(menu.console.lines)
    assert 'Configuration: Configured' in output
    assert 'Hostname: sensor.example.com' in output
    assert 'Tunnel: sensor-tunnel' in output
    assert 'Runtime: Running' in output
    assert 'Readiness: No Edge' in output
    assert 'Authorized users: operator-one, operator-two' in output
    assert 'ready connections=0' in output
    assert 'Last error: 2026-09-17T11:59:00Z — connection refused' in output
    assert '2026-09-17T11:58:00Z [tls] certificate rejected' in output
    assert menu.paused is True


def test_tunnel_status_rejects_legacy_agent_without_api_call():
    menu = Menu(V1Agent())

    handle_tunnel(menu, ['status'])

    assert menu.sdk.aegis.calls == []
    assert 'available only for Aegis v2 endpoints' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_tunnel_status_rejects_yes_option():
    menu = Menu(V2Endpoint())

    handle_tunnel(menu, ['status', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert '--yes is only valid' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_tunnel_create_uses_selected_v2_endpoint_uuid_without_legacy_access():
    menu = Menu(V2Endpoint())

    handle_tunnel(menu, ['create', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'create_cloudflare_tunnel',
        'endpoint_id': 'endpoint-1',
        'legacy': False,
    }]
    output = '\n'.join(menu.console.lines)
    assert 'Cloudflare tunnel install queued' in output
    assert 'Agent: endpoint-1' in output
    assert menu.paused is True


def test_tunnel_remove_uses_selected_v2_endpoint_uuid_without_legacy_access():
    menu = Menu(V2Endpoint())

    handle_tunnel(menu, ['remove', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'remove_cloudflare_tunnel',
        'endpoint_id': 'endpoint-1',
        'legacy': False,
    }]
    output = '\n'.join(menu.console.lines)
    assert 'Cloudflare tunnel removal queued' in output
    assert 'Agent: endpoint-1' in output
    assert menu.paused is True


def test_tunnel_cancel_does_not_call_api(monkeypatch):
    menu = Menu(V2Endpoint())
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.tunnel.Confirm.ask', lambda *a, **k: False)

    handle_tunnel(menu, ['create'])

    assert menu.sdk.aegis.calls == []
    assert 'Cancelled' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_tunnel_create_uses_selected_v1_client_id():
    menu = Menu(V1Agent())

    handle_tunnel(menu, ['create', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'create_cloudflare_tunnel',
        'endpoint_id': 'C.1',
        'legacy': True,
    }]
    assert 'Agent: C.1' in '\n'.join(menu.console.lines)


def test_tunnel_requires_selected_agent():
    menu = Menu()

    handle_tunnel(menu, ['create', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert 'No Aegis agent selected' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_tunnel_completion_for_v1_and_v2_agents():
    assert complete(Menu(V2Endpoint()), 'st', ['tunnel']) == ['status']
    assert complete(Menu(V2Endpoint()), 'cr', ['tunnel']) == ['create']
    assert complete(Menu(V2Endpoint()), '--', ['tunnel', 'status']) == ['--help']
    assert complete(Menu(V2Endpoint()), '--', ['tunnel', 'create']) == ['--yes', '--help']
    assert complete(Menu(V1Agent()), 'cr', ['tunnel']) == ['create']
    assert complete(Menu(V1Agent()), 'st', ['tunnel']) == []
