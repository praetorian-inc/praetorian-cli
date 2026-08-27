import pytest

from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK
from praetorian_cli.ui.aegis.commands.user import complete, handle_user

pytestmark = pytest.mark.tui


class V2Endpoint:
    hostname = 'sensor'
    endpoint_id = 'endpoint-1'
    version = 'v2'

    @property
    def client_id(self):
        raise AssertionError('v2 user commands must not inspect legacy client_id')

    @property
    def has_tunnel(self):
        raise AssertionError('v2 user commands must not inspect legacy tunnel state')

    @property
    def health_check(self):
        raise AssertionError('v2 user commands must not inspect legacy tunnel state')


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


@pytest.mark.parametrize('username', ['pentester', 'alice.smith'])
def test_user_add_uses_selected_v2_endpoint_uuid_without_legacy_access(username):
    menu = Menu(V2Endpoint())

    handle_user(menu, ['add', username, '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'add_system_user',
        'endpoint_id': 'endpoint-1',
        'username': username,
    }]
    output = '\n'.join(menu.console.lines)
    assert 'User add queued' in output
    assert 'Endpoint: endpoint-1' in output
    assert f'Username: {username}' in output
    assert menu.paused is True


def test_user_remove_uses_selected_v2_endpoint_uuid_without_legacy_access():
    menu = Menu(V2Endpoint())

    handle_user(menu, ['remove', 'pentester', '--remove-home', '--yes'])

    assert menu.sdk.aegis.calls == [{
        'method': 'remove_system_user',
        'endpoint_id': 'endpoint-1',
        'username': 'pentester',
        'remove_home': True,
    }]
    output = '\n'.join(menu.console.lines)
    assert 'User removal queued' in output
    assert 'Endpoint: endpoint-1' in output
    assert 'Username: pentester' in output
    assert menu.paused is True


def test_user_cancel_does_not_call_api(monkeypatch):
    menu = Menu(V2Endpoint())
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.user.Confirm.ask', lambda *a, **k: False)

    handle_user(menu, ['add', 'pentester'])

    assert menu.sdk.aegis.calls == []
    assert 'Cancelled' in '\n'.join(menu.console.lines)
    assert menu.paused is True


@pytest.mark.parametrize('selected_agent', [None, V1Agent()])
def test_user_requires_selected_v2_endpoint(selected_agent):
    menu = Menu(selected_agent)

    handle_user(menu, ['add', 'pentester', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert 'No Aegis v2 endpoint selected' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_user_rejects_invalid_username_before_api_call():
    menu = Menu(V2Endpoint())

    handle_user(menu, ['add', 'bad;name', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert 'invalid Linux username' in '\n'.join(menu.console.lines)
    assert menu.paused is True


def test_user_completion_only_for_selected_v2_endpoint():
    assert complete(Menu(V2Endpoint()), 'ad', ['user']) == ['add']
    assert complete(Menu(V2Endpoint()), '--', ['user', 'remove', 'pentester']) == ['--remove-home', '--yes', '--help']
    assert complete(Menu(V1Agent()), 'ad', ['user']) == []
