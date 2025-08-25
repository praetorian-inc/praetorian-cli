import pytest
from praetorian_cli.ui.aegis.commands.set import handle_set
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase

pytestmark = pytest.mark.tui


class MockAgent:
    def __init__(self, hostname, client_id):
        self.hostname = hostname
        self.client_id = client_id


class Menu(MockMenuBase):
    def __init__(self, agents):
        super().__init__()
        self.agents = agents
        self.selected_agent = None


def test_set_no_args_shows_message_and_pauses():
    menu = Menu([MockAgent("a1", "C.1"), MockAgent("a2", "C.2")])
    handle_set(menu, [])
    assert any("No agent selected" in l for l in menu.console.lines)
    assert menu.paused is True


def test_set_by_index_selects_agent():
    a1 = MockAgent("a1", "C.1")
    a2 = MockAgent("a2", "C.2")
    menu = Menu([a1, a2])
    handle_set(menu, ["2"])  # 1-based index
    assert menu.selected_agent is a2
    assert any("Selected: a2" in l for l in menu.console.lines)


def test_set_by_hostname_selects_agent():
    a1 = MockAgent("alpha", "C.1")
    a2 = MockAgent("bravo", "C.2")
    menu = Menu([a1, a2])
    handle_set(menu, ["bravo"])
    assert menu.selected_agent is a2


def test_set_by_client_id_selects_agent():
    a1 = MockAgent("alpha", "C.1")
    a2 = MockAgent("bravo", "C.2")
    menu = Menu([a1, a2])
    handle_set(menu, ["C.1"])
    assert menu.selected_agent is a1


def test_set_not_found_shows_error_and_pauses():
    menu = Menu([MockAgent("a1", "C.1")])
    handle_set(menu, ["missing"])
    assert any("Agent not found" in l for l in menu.console.lines)
    assert menu.paused is True
