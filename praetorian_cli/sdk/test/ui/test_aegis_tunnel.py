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


def test_tunnel_create_uses_selected_v2_endpoint_uuid_without_legacy_access():
    menu = Menu(V2Endpoint())

    handle_tunnel(menu, ['create', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'create_cloudflare_tunnel',
        'endpoint_id': 'endpoint-1',
    }]
    output = '\n'.join(menu.console.lines)
    assert 'Cloudflare tunnel install queued' in output
    assert 'Endpoint: endpoint-1' in output
    assert menu.paused is True


def test_tunnel_remove_uses_selected_v2_endpoint_uuid_without_legacy_access():
    menu = Menu(V2Endpoint())

    handle_tunnel(menu, ['remove', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'remove_cloudflare_tunnel',
        'endpoint_id': 'endpoint-1',
    }]
    output = '\n'.join(menu.console.lines)
    assert 'Cloudflare tunnel removal queued' in output
    assert 'Endpoint: endpoint-1' in output
    assert menu.paused is True


def test_tunnel_cancel_does_not_call_api(monkeypatch):
    menu = Menu(V2Endpoint())
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.tunnel.Confirm.ask', lambda *a, **k: False)

    handle_tunnel(menu, ['create'])

    assert menu.sdk.aegis.calls == []
    assert 'Cancelled' in '\n'.join(menu.console.lines)
    assert menu.paused is True


@pytest.mark.parametrize('selected_agent', [None, V1Agent()])
def test_tunnel_requires_selected_v2_endpoint(selected_agent):
    menu = Menu(selected_agent)

    handle_tunnel(menu, ['create', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert 'No Aegis v2 endpoint selected' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_tunnel_completion_only_for_selected_v2_endpoint():
    assert complete(Menu(V2Endpoint()), 'cr', ['tunnel']) == ['create']
    assert complete(Menu(V2Endpoint()), '--', ['tunnel', 'create']) == ['--yes', '--help']
    assert complete(Menu(V1Agent()), 'cr', ['tunnel']) == []
