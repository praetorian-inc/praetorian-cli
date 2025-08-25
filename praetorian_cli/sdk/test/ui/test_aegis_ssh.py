import pytest
from praetorian_cli.ui.aegis.commands.ssh import handle_ssh
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = MockAgent()


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


def test_handle_ssh_user_extraction_and_strip_l_flag():
    menu = Menu()
    args = ["-u", "admin", "-L", "8080:localhost:80", "-l", "ignored"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] == "admin"
    assert call['options'] == ["-L", "8080:localhost:80", "-L", "ignored"]


def test_handle_ssh_user_equals_form():
    menu = Menu()
    args = ["--user=alice", "-D", "1080"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] is None
    assert call['options'] == ["--user=alice", "-D", "1080"]


def test_handle_ssh_no_user_allows_native_l():
    menu = Menu()
    args = ["-l", "bob", "-i", "~/.ssh/id_ed25519"]
    handle_ssh(menu, args)

    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] is None
    assert call['options'] == ["-L", "bob", "-i", "~/.ssh/id_ed25519"]
