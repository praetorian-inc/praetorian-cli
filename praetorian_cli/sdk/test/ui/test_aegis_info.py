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


def test_info_error_path():
    agent = ErrorAgent("irrelevant")
    menu = Menu(agent=agent)
    handle_info(menu, [])
    assert any("Error getting agent info" in l for l in menu.console.lines)
    assert menu.paused is True
