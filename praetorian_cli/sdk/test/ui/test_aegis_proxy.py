import pytest
from unittest.mock import patch, MagicMock
from threading import Event

from praetorian_cli.ui.aegis.commands.proxy import (
    handle_proxy,
    stop_all_proxies,
    _format_uptime,
    complete,
    ProxyInfo,
)
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = MockAgent()
        self._active_proxies = {}


# --- help ---

def test_help_explicit():
    menu = Menu()
    handle_proxy(menu, ['help'])
    assert any('Proxy Command' in line for line in menu.console.lines)


def test_help_no_args():
    menu = Menu()
    handle_proxy(menu, [])
    assert any('Proxy Command' in line for line in menu.console.lines)


def test_help_dash_h():
    menu = Menu()
    handle_proxy(menu, ['-h'])
    assert any('Proxy Command' in line for line in menu.console.lines)


# --- validation ---

def test_no_agent_selected():
    menu = Menu()
    menu.selected_agent = None
    handle_proxy(menu, ['1080'])
    assert any('No agent selected' in line for line in menu.console.lines)


def test_no_tunnel():
    menu = Menu()
    menu.selected_agent.has_tunnel = False
    handle_proxy(menu, ['1080'])
    assert any('no active tunnel' in line for line in menu.console.lines)


def test_invalid_port_string():
    menu = Menu()
    handle_proxy(menu, ['abc'])
    assert any('Invalid port' in line for line in menu.console.lines)


def test_port_out_of_range():
    menu = Menu()
    handle_proxy(menu, ['99999'])
    assert any('between 1 and 65535' in line for line in menu.console.lines)


def test_port_zero():
    menu = Menu()
    handle_proxy(menu, ['0'])
    assert any('between 1 and 65535' in line for line in menu.console.lines)


# --- start ---

@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_start_success(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None  # still running
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])

    assert 1080 in menu._active_proxies
    assert any('started' in line for line in menu.console.lines)
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args[0][0]
    assert '-D' in cmd
    assert '1080' in cmd


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_start_with_user(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['8080', '-u', 'admin'])

    assert 8080 in menu._active_proxies
    cmd = mock_popen.call_args[0][0]
    assert any('admin@' in arg for arg in cmd)


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_port_conflict(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    mock_popen.return_value = proc

    menu = Menu()
    # Start first proxy
    handle_proxy(menu, ['1080'])
    assert 1080 in menu._active_proxies

    # Try starting same port
    handle_proxy(menu, ['1080'])
    assert any('already running' in line for line in menu.console.lines)


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_immediate_failure(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = 1  # exited immediately
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])
    assert 1080 not in menu._active_proxies
    assert any('Failed to start' in line for line in menu.console.lines)


# --- list ---

def test_list_empty():
    menu = Menu()
    handle_proxy(menu, ['list'])
    assert any('No active proxies' in line for line in menu.console.lines)


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_list_with_entries(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])
    menu.console.lines.clear()

    handle_proxy(menu, ['list'])
    # MockConsole stores Rich Table objects; verify a table was printed
    # and "No active proxies" was NOT printed
    assert not any('No active proxies' in line for line in menu.console.lines)
    assert any('Table' in str(type(line)) or 'Table' in line for line in menu.console.lines)


# --- stop ---

@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_stop_port(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.return_value = 0
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])
    assert 1080 in menu._active_proxies

    handle_proxy(menu, ['stop', '1080'])
    assert 1080 not in menu._active_proxies
    proc.terminate.assert_called()


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_stop_all(mock_popen):
    proc1 = MagicMock()
    proc1.poll.return_value = None
    proc1.wait.return_value = 0
    proc2 = MagicMock()
    proc2.poll.return_value = None
    proc2.wait.return_value = 0
    mock_popen.side_effect = [proc1, proc2]

    menu = Menu()
    handle_proxy(menu, ['1080'])
    handle_proxy(menu, ['9050'])
    assert len(menu._active_proxies) == 2

    handle_proxy(menu, ['stop', 'all'])
    assert len(menu._active_proxies) == 0


def test_stop_nonexistent():
    menu = Menu()
    handle_proxy(menu, ['stop', '9999'])
    assert any('No proxy running' in line for line in menu.console.lines)


def test_stop_missing_arg():
    menu = Menu()
    handle_proxy(menu, ['stop'])
    assert any('Usage' in line for line in menu.console.lines)


# --- stop_all_proxies cleanup ---

@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_stop_all_proxies_cleanup(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.return_value = 0
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])
    assert 1080 in menu._active_proxies

    stop_all_proxies(menu)
    assert len(menu._active_proxies) == 0
    proc.terminate.assert_called()


# --- _format_uptime ---

def test_format_uptime_seconds():
    assert _format_uptime(45) == '45s'
    assert _format_uptime(0) == '0s'
    assert _format_uptime(59) == '59s'


def test_format_uptime_minutes():
    assert _format_uptime(60) == '1m'
    assert _format_uptime(180) == '3m'
    assert _format_uptime(3599) == '59m'


def test_format_uptime_hours():
    assert _format_uptime(3600) == '1h'
    assert _format_uptime(4800) == '1h20m'
    assert _format_uptime(7200) == '2h'


# --- tab completion ---

def test_complete_subcommands():
    menu = Menu()
    result = complete(menu, '', [])
    assert 'list' in result
    assert 'stop' in result
    assert 'help' in result


def test_complete_subcommand_prefix():
    menu = Menu()
    result = complete(menu, 'li', [])
    assert result == ['list']


@patch('praetorian_cli.ui.aegis.commands.proxy.subprocess.Popen')
def test_complete_stop_ports(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    mock_popen.return_value = proc

    menu = Menu()
    handle_proxy(menu, ['1080'])

    result = complete(menu, '', ['proxy', 'stop'])
    assert 'all' in result
    assert '1080' in result
