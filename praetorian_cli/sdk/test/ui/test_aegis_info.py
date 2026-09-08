import pytest
from praetorian_cli.ui.aegis.commands.info import handle_info
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockAgent

pytestmark = pytest.mark.tui
class ErrorAgent(MockAgent):
    def __init__(self, hostname="agent01", client_id="C.1"):
        # Intentionally avoid calling super().__init__ to control attributes
        self.hostname = hostname
        self.client_id = client_id
        # Set minimal attributes expected by the renderer
        self.os = None
        self.os_version = None
        self.architecture = None
        self.fqdn = None
        self.network_interfaces = []
        self.has_tunnel = False
        self.health_check = None

    # Create an attribute whose access raises to simulate a rendering error
    @property
    def last_seen_at(self):
        raise RuntimeError("boom")


class Menu(MockMenuBase):
    def __init__(self, agent=None):
        super().__init__()
        self.selected_agent = agent


def test_info_no_selected_agent():
    menu = Menu(agent=None)
    handle_info(menu, [])
    assert any("No agent selected" in l for l in menu.console.lines)
    assert menu.paused is True


def test_info_prints_detail():
    agent = MockAgent(hostname="Agent-01")
    menu = Menu(agent=agent)
    handle_info(menu, [])
    assert any("Agent Details" in l for l in menu.console.lines)
    assert any("Agent-01" in l for l in menu.console.lines)
    assert menu.paused is True


def test_info_prints_v2_endpoint_identity_and_account():
    agent = MockAgent(hostname="sensor")
    agent.version = "v2"
    agent.endpoint_id = "endpoint-1"
    agent.client_id = "N/A"
    agent._account_info = {"display_name": "Gladiator"}
    menu = Menu(agent=agent)

    handle_info(menu, [])

    output = "\n".join(menu.console.lines)
    assert "Version:      v2" in output
    assert "Endpoint ID:  endpoint-1" in output
    assert "Account:      Gladiator" in output
    assert "Client ID:" not in output
    assert menu.paused is True


def test_info_v2_endpoint_does_not_read_legacy_client_id():
    class V2Endpoint:
        hostname = "sensor"
        endpoint_id = "endpoint-1"
        version = "v2"
        os = "linux"
        os_version = ""
        architecture = "amd64"
        fqdn = "sensor"
        last_seen_at = 0
        network_interfaces = []
        health_check = None

        @property
        def client_id(self):
            raise AssertionError("v2 info must not inspect legacy client_id")

    menu = Menu(agent=V2Endpoint())

    handle_info(menu, [])

    output = "\n".join(menu.console.lines)
    assert "Endpoint ID:  endpoint-1" in output
    assert "Error getting agent info" not in output
    assert menu.paused is True


def test_info_error_path():
    agent = ErrorAgent("irrelevant")
    menu = Menu(agent=agent)
    handle_info(menu, [])
    assert any("Error getting agent info" in l for l in menu.console.lines)
    assert menu.paused is True
