import pytest
from praetorian_cli.ui.aegis.commands.info import handle_info
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase

pytestmark = pytest.mark.tui
class MockAgent:
    def __init__(self, detail):
        self._detail = detail

    def to_detailed_string(self):
        return self._detail

class ErrorAgent(MockAgent):
    def to_detailed_string(self):
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
    agent = MockAgent("Agent detail text")
    menu = Menu(agent=agent)
    handle_info(menu, [])
    assert any("Agent detail text" in l for l in menu.console.lines)
    assert menu.paused is True


def test_info_error_path():
    agent = ErrorAgent("irrelevant")
    menu = Menu(agent=agent)
    handle_info(menu, [])
    assert any("Error getting agent info" in l for l in menu.console.lines)
    assert menu.paused is True
