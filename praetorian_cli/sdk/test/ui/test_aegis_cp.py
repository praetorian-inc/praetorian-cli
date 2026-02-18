from unittest.mock import patch, MagicMock
import pytest
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from praetorian_cli.ui.aegis.commands.cp import handle_cp
from praetorian_cli.ui.aegis.menu import MenuCompleter, _remote_ls_lookup_or_fetch
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = MockAgent()
        # Remote file listing state (mirrors AegisMenu)
        self._remote_ls_cache = {}
        self._remote_ls_pending = set()

    def prefetch_agent_home(self, agent=None):
        agent = agent or self.selected_agent
        if not agent or not getattr(agent, 'has_tunnel', False):
            return
        try:
            public_hostname = agent.health_check.cloudflared_status.hostname
            if not public_hostname:
                return
        except Exception:
            return
        client_id = getattr(agent, 'client_id', '') or ''
        for directory in ('~', '/tmp'):
            _remote_ls_lookup_or_fetch(
                self, (client_id, directory), public_hostname, directory,
            )


def test_handle_cp_help_message():
    menu = Menu()
    handle_cp(menu, ["help"])
    assert any("CP Command" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_dash_h_message():
    menu = Menu()
    handle_cp(menu, ["-h"])
    assert any("CP Command" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_upload():
    menu = Menu()
    handle_cp(menu, ["./local.txt", ":/tmp/remote.txt"])
    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['method'] == 'copy_to_agent'
    assert call['direction'] == 'upload'
    assert call['local_path'] == './local.txt'
    assert call['remote_path'] == '/tmp/remote.txt'


def test_handle_cp_download():
    menu = Menu()
    handle_cp(menu, [":/etc/passwd", "./loot/passwd"])
    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['method'] == 'copy_to_agent'
    assert call['direction'] == 'download'
    assert call['local_path'] == './loot/passwd'
    assert call['remote_path'] == '/etc/passwd'


def test_handle_cp_both_remote_error():
    menu = Menu()
    handle_cp(menu, [":/remote1", ":/remote2"])
    assert any("both paths cannot be remote" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_neither_remote_error():
    menu = Menu()
    handle_cp(menu, ["./local1", "./local2"])
    assert any("one path must be remote" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_no_agent_selected():
    menu = Menu()
    menu.selected_agent = None
    handle_cp(menu, ["./file", ":/tmp/file"])
    assert any("No agent selected" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_wrong_arg_count():
    menu = Menu()
    handle_cp(menu, ["./only_one_path"])
    assert any("exactly two paths" in l for l in menu.console.lines)
    assert len(menu.sdk.aegis.calls) == 0


def test_handle_cp_user_option():
    menu = Menu()
    handle_cp(menu, ["-u", "root", "./file", ":/tmp/file"])
    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['user'] == 'root'
    assert call['direction'] == 'upload'


def test_handle_cp_no_rsync_flag():
    menu = Menu()
    handle_cp(menu, ["--no-rsync", "./file", ":/tmp/file"])
    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['use_rsync'] is False


def test_handle_cp_identity_option():
    menu = Menu()
    handle_cp(menu, ["-i", "~/.ssh/id_rsa", "./file", ":/tmp/file"])
    assert len(menu.sdk.aegis.calls) == 1
    call = menu.sdk.aegis.calls[0]
    assert call['ssh_options'] == ['-i', '~/.ssh/id_rsa']


def test_cp_completion_returns_file_paths(tmp_path):
    """Tab-completing a local path argument for 'cp' yields file path results."""
    # Create a temp file so PathCompleter has something to find
    test_file = tmp_path / "testfile.txt"
    test_file.write_text("data")

    menu = Menu()
    menu.commands = ['cp']
    completer = MenuCompleter(menu)

    # Simulate typing: cp <tmp_path>/test
    text = f"cp {tmp_path}/test"
    doc = Document(text, len(text))
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    # PathCompleter returns the suffix to append (e.g. "file.txt" for "test" -> "testfile.txt")
    # Check display text which shows the full filename
    displays = [c.display for c in completions]
    assert len(completions) > 0
    assert any("testfile.txt" in str(d) for d in displays)


def test_cp_completion_option_flags():
    """Tab-completing flags for 'cp' yields option completions."""
    menu = Menu()
    menu.commands = ['cp']
    completer = MenuCompleter(menu)

    text = "cp --no"
    doc = Document(text, len(text))
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert '--no-rsync' in texts


def test_cp_completion_skips_remote_paths_without_agent():
    """Remote paths yield no completions when no agent is selected."""
    menu = Menu()
    menu.selected_agent = None
    menu.commands = ['cp']
    completer = MenuCompleter(menu)

    text = "cp :/tmp/rem"
    doc = Document(text, len(text))
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    assert completions == []


def test_cp_completion_remote_paths_via_ssh():
    """Remote paths complete by listing files on the agent via SSH (async fetch)."""
    import time as _time
    menu = Menu()
    menu.commands = ['cp']
    menu.sdk.aegis.api = MagicMock()
    menu.sdk.aegis.api.get_current_user.return_value = ('user@example.com', 'testuser')

    completer = MenuCompleter(menu)

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "remote_file.txt\nbackups/\nremote_log.txt\n"

    with patch('praetorian_cli.ui.aegis.menu.subprocess.run', return_value=fake_result) as mock_run:
        text = "cp :/tmp/remote"
        doc = Document(text, len(text))
        event = CompleteEvent()

        # First call fires background thread, returns nothing (toolbar shows loading)
        completions = list(completer.get_completions(doc, event))
        assert completions == []

        # Wait for background thread to populate cache (on the menu, not completer)
        for _ in range(50):
            if ('C.1', '/tmp') in menu._remote_ls_cache:
                break
            _time.sleep(0.05)

        # Second call returns cached results
        completions = list(completer.get_completions(doc, event))

    assert mock_run.called
    ssh_cmd = mock_run.call_args[0][0]
    assert 'ssh' in ssh_cmd[0]
    assert 'ls -1F /tmp' in ' '.join(ssh_cmd)

    texts = [c.text for c in completions]
    assert any('remote_file.txt' in t for t in texts)
    assert any('remote_log.txt' in t for t in texts)
    assert not any('backups' in t for t in texts)


def test_cp_completion_remote_caches_results():
    """Repeated remote completions in the same directory use cached SSH results."""
    import time as _time
    menu = Menu()
    menu.commands = ['cp']
    menu.sdk.aegis.api = MagicMock()
    menu.sdk.aegis.api.get_current_user.return_value = ('user@example.com', 'testuser')

    completer = MenuCompleter(menu)

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "file_a.txt\nfile_b.txt\n"

    with patch('praetorian_cli.ui.aegis.menu.subprocess.run', return_value=fake_result) as mock_run:
        text = "cp :/home/file_a"
        doc = Document(text, len(text))

        # First call fires background thread
        list(completer.get_completions(doc, CompleteEvent()))

        # Wait for background thread (cache lives on menu)
        for _ in range(50):
            if ('C.1', '/home') in menu._remote_ls_cache:
                break
            _time.sleep(0.05)

        # Second call uses cache
        completions1 = list(completer.get_completions(doc, CompleteEvent()))

        # Different prefix, same directory — still cached
        text = "cp :/home/file_b"
        doc = Document(text, len(text))
        completions2 = list(completer.get_completions(doc, CompleteEvent()))

    # SSH should only have been called once
    assert mock_run.call_count == 1
    assert len(completions1) > 0
    assert len(completions2) > 0


def test_set_prefetches_agent_home():
    """Selecting an agent via 'set' prefetches ~ so cp completions are instant."""
    import time as _time
    from praetorian_cli.ui.aegis.commands.set import handle_set

    menu = Menu()
    menu.commands = ['set', 'cp']
    menu.displayed_agents = [MockAgent()]
    menu.agents = menu.displayed_agents
    menu._remote_ls_cache = {}
    menu._remote_ls_pending = set()
    menu.sdk.aegis.api = MagicMock()
    menu.sdk.aegis.api.get_current_user.return_value = ('u@example.com', 'testuser')

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "Documents/\nfile.txt\n"

    with patch('praetorian_cli.ui.aegis.menu.subprocess.run', return_value=fake_result):
        handle_set(menu, ['1'])

        # Wait for background prefetch
        for _ in range(50):
            if ('C.1', '~') in menu._remote_ls_cache:
                break
            _time.sleep(0.05)

    assert ('C.1', '~') in menu._remote_ls_cache
    _, entries = menu._remote_ls_cache[('C.1', '~')]
    assert 'Documents/' in entries
    assert 'file.txt' in entries
