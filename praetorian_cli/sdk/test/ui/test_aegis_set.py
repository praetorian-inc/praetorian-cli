import pytest
from rich.console import Console
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from praetorian_cli.ui.aegis.commands.set import handle_set
from praetorian_cli.ui.aegis.menu import AegisMenu, MenuCompleter
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase

pytestmark = pytest.mark.tui


class MockAgent:
    def __init__(self, hostname, client_id, endpoint_id=None):
        self.hostname = hostname
        self.client_id = client_id
        self.endpoint_id = endpoint_id
        self.version = 'v2' if endpoint_id else 'v1'


class MockAccounts:
    def __init__(self):
        self.assumed = []

    def assume_role(self, account_email):
        self.assumed.append(account_email)


class MockSDK:
    def __init__(self):
        self.accounts = MockAccounts()

    def get_current_user(self):
        return 'operator@praetorian.com', 'operator'


class Menu(MockMenuBase):
    def __init__(self, agents):
        super().__init__()
        self.agents = agents
        self.selected_agent = None
        self.displayed_agents = agents
        self.commands = ['set']
        self.sdk = MockSDK()


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


def test_set_by_endpoint_id_selects_v2_agent():
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = Menu([v2_agent])

    handle_set(menu, ["endpoint-1"])

    assert menu.selected_agent is v2_agent
    assert any("[v2] (endpoint-1)" in l for l in menu.console.lines)


def test_set_v2_label_renders_literal_version_in_rich_console():
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = Menu([v2_agent])
    menu.console = Console(record=True, force_terminal=False, width=80)

    handle_set(menu, ["endpoint-1"])

    assert "Selected: sensor [v2] (endpoint-1)" in menu.console.export_text()


def test_set_by_index_selects_v2_agent():
    v1_agent = MockAgent("agent", "C.1")
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = Menu([v1_agent, v2_agent])

    handle_set(menu, ["2"])

    assert menu.selected_agent is v2_agent


def test_set_by_unique_hostname_selects_v2_agent():
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = Menu([MockAgent("agent", "C.1"), v2_agent])

    handle_set(menu, ["sensor"])

    assert menu.selected_agent is v2_agent


def test_set_ambiguous_hostname_fails_with_actionable_prompt():
    menu = Menu([
        MockAgent("shared", "C.1"),
        MockAgent("shared", "N/A", endpoint_id="endpoint-1"),
    ])

    handle_set(menu, ["shared"])

    assert menu.selected_agent is None
    assert any("Multiple agents match hostname" in l for l in menu.console.lines)
    assert any("endpoint ID" in l for l in menu.console.lines)
    assert menu.paused is True


def test_set_v2_endpoint_assumes_account_by_endpoint_id():
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = Menu([v2_agent])
    menu.multi_account_mode = True
    menu.agent_account_map = {
        "endpoint-1": {
            "account_email": "gladiator@praetorian.com",
            "display_name": "Gladiator",
        }
    }

    handle_set(menu, ["endpoint-1"])

    assert menu.selected_agent is v2_agent
    assert menu.selected_agent.endpoint_id == "endpoint-1"
    assert menu.selected_agent.version == "v2"
    assert menu.selected_agent._account_info["display_name"] == "Gladiator"
    assert menu.sdk.accounts.assumed == ["gladiator@praetorian.com"]
    assert any("Gladiator" in l for l in menu.console.lines)


def test_set_completion_includes_v2_endpoint_id():
    menu = Menu([MockAgent("agent", "C.1"), MockAgent("sensor", "N/A", endpoint_id="endpoint-1")])
    completer = MenuCompleter(menu)
    doc = Document("set endpoint", len("set endpoint"))

    completions = list(completer.get_completions(doc, CompleteEvent()))

    assert "endpoint-1" in [completion.text for completion in completions]


def test_prompt_identifies_selected_v2_endpoint_and_account(monkeypatch):
    v2_agent = MockAgent("sensor", "N/A", endpoint_id="endpoint-1")
    menu = AegisMenu(MockSDK())
    menu.selected_agent = v2_agent
    menu.agent_account_map = {
        "endpoint-1": {"account_email": "gladiator@praetorian.com"}
    }

    captured = {}

    def fake_prompt(prompt, **_kwargs):
        captured['prompt'] = prompt
        return "info"

    monkeypatch.setattr('praetorian_cli.ui.aegis.menu.pt_prompt', fake_prompt)

    assert menu.get_input() == "info"
    assert captured['prompt'] == "sensor [v2 | gladiator@praetorian.com]> "


def test_set_not_found_shows_error_and_pauses():
    menu = Menu([MockAgent("a1", "C.1")])
    handle_set(menu, ["missing"])
    assert any("Agent not found" in l for l in menu.console.lines)
    assert menu.paused is True
