import pytest
from praetorian_cli.ui.aegis.commands.ssh import handle_ssh
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent, MockHealthCheck, MockCloudflaredStatus

pytestmark = pytest.mark.tui


class V2Endpoint:
    hostname = "sensor"
    endpoint_id = "endpoint-1"
    version = "v2"
    has_tunnel = True
    health_check = MockHealthCheck(MockCloudflaredStatus('endpoint.example.com', 'endpoint-tunnel'))

    @property
    def client_id(self):
        raise AssertionError('v2 ssh must not inspect legacy client_id')


class Menu(MockMenuBase):
    def __init__(self, selected_agent=None):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = selected_agent or MockAgent()


class RefreshingMenu(Menu):
    def __init__(self, stale_agent, fresh_agent):
        super().__init__(stale_agent)
        self.fresh_agent = fresh_agent
        self.refresh_calls = 0

    def refresh_selected_agent(self):
        self.refresh_calls += 1
        self.selected_agent = self.fresh_agent
        return self.selected_agent


def test_handle_ssh_help_message():
    menu = Menu()
    handle_ssh(menu, ["help"])  # explicit 'help'
    assert any("SSH Command" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_ssh_dash_h_message():
    menu = Menu()
    handle_ssh(menu, ["-h"])  # short help
    assert any("SSH Command" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_ssh_l_flag_sets_user_without_forwarding():
    menu = Menu()
    args = ["-L", "8080:localhost:80", "-l", "admin"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] == "admin"
    assert call['options'] == ["-L", "8080:localhost:80"]


def test_handle_ssh_user_equals_form():
    menu = Menu()
    args = ["--user=alice", "-D", "1080"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] == "alice"
    assert call['options'] == ["-D", "1080"]


def test_handle_ssh_no_user_allows_native_l():
    menu = Menu()
    args = ["-l", "bob", "-i", "~/.ssh/id_ed25519"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] == "bob"
    assert call['options'] == ["-i", "~/.ssh/id_ed25519"]


def test_handle_ssh_accepts_selected_v2_endpoint_without_legacy_client_id_access():
    menu = Menu(V2Endpoint())

    handle_ssh(menu, [])

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['method'] == 'ssh_to_agent'
    assert call['agent'] is menu.selected_agent
    assert call['user'] is None


def test_handle_ssh_refreshes_selected_agent_before_validation():
    stale_agent = MockAgent(hostname="sensor", client_id="N/A")
    stale_agent.version = "v2"
    stale_agent.endpoint_id = "endpoint-1"
    stale_agent.has_tunnel = False
    stale_agent.health_check = None

    fresh_agent = MockAgent(hostname="sensor", client_id="N/A")
    fresh_agent.version = "v2"
    fresh_agent.endpoint_id = "endpoint-1"
    fresh_agent.has_tunnel = True
    fresh_agent.health_check = MockHealthCheck(MockCloudflaredStatus('endpoint.example.com', 'endpoint-tunnel'))

    menu = RefreshingMenu(stale_agent, fresh_agent)

    handle_ssh(menu, [])

    assert menu.refresh_calls == 1
    assert len(menu.sdk.aegis.calls) == 1
    assert menu.sdk.aegis.calls[0]['agent'] is fresh_agent
