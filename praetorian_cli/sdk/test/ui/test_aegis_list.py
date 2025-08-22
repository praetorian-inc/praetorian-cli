import pytest
from praetorian_cli.ui.aegis.commands.list import handle_list
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, agents=None):
        super().__init__()
        self.agents = agents or []
        self.loaded = False
        self.show_args = []

    def load_agents(self):
        self.loaded = True
        self.agents = [object()]

    def show_agents_list(self, show_offline=False):
        self.show_args.append(show_offline)


def test_list_loads_when_empty():
    menu = Menu(agents=[])
    handle_list(menu, [])
    assert menu.loaded is True
    assert menu.show_args == [False]
    assert menu.paused is True


def test_list_with_all_flag():
    menu = Menu(agents=[object()])
    handle_list(menu, ['--all'])
    assert menu.loaded is False
    assert menu.show_args == [True]
    assert menu.paused is True
