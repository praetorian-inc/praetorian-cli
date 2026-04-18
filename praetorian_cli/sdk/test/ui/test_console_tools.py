"""Unit tests for console `run` passthrough and local execution path."""
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.ui.console.commands.tools import ToolCommands
from praetorian_cli.sdk.test.ui_mocks import MockConsole

pytestmark = pytest.mark.tui


class _FakeContext:
    active_tool = None
    account = 'acct'
    _last_job_key = ''

    def apply_scope_to_message(self, msg):
        return msg


class _Harness(ToolCommands):
    """Bare wrapper to exercise ToolCommands methods in isolation."""

    def __init__(self, sdk=None):
        self.console = MockConsole()
        self.sdk = sdk or MagicMock()
        self.context = _FakeContext()
        self.colors = {
            'primary': 'cyan', 'accent': 'magenta', 'dim': 'dim',
            'info': 'blue', 'success': 'green', 'warning': 'yellow', 'error': 'red',
        }

    # Stubs for methods the real console provides elsewhere.
    def _send_to_marcus(self, message):  # pragma: no cover — not used in these tests
        return ''

    def _wait_for_job(self, *a, **kw):
        pass


def test_run_with_passthrough_executes_locally_when_installed():
    h = _Harness()
    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch.object(_Harness, '_run_tool_locally') as mock_local:
        h._cmd_run(['brutus', '10.0.1.5:22', '--protocol', 'ssh', '-U', 'users.txt'])

    assert mock_local.called
    args, kwargs = mock_local.call_args
    # Expect (tool_name, target, pass_through)
    assert args[0] == 'brutus'
    assert args[1] == '10.0.1.5:22'
    assert list(args[2]) == ['--protocol', 'ssh', '-U', 'users.txt']


def test_run_with_passthrough_but_not_installed_errors():
    h = _Harness()
    with patch('praetorian_cli.runners.local.is_installed', return_value=False):
        h._cmd_run(['brutus', '10.0.1.5:22', '--protocol', 'ssh'])
    output = '\n'.join(h.console.lines)
    assert 'install' in output.lower() or 'local' in output.lower()


def test_double_dash_forwards_own_flags():
    """After `--`, even console-owned flags like --wait pass through."""
    h = _Harness()
    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch.object(_Harness, '_run_tool_locally') as mock_local:
        h._cmd_run(['brutus', '10.0.1.5:22', '--', '--wait', '--spray'])
    args, _ = mock_local.call_args
    assert list(args[2]) == ['--wait', '--spray']


def test_own_wait_flag_routes_to_remote_with_wait():
    """`run brutus x --wait` (no `--`) keeps --wait as a console flag and routes remote."""
    h = _Harness()
    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch.object(_Harness, '_try_queue_job', return_value=[{'key': '#job#x'}]) as mock_queue, \
         patch.object(_Harness, '_wait_for_job') as mock_wait:
        h._cmd_run(['brutus', '#asset#10.0.1.5', '--wait'])
    assert mock_queue.called
    assert mock_wait.called


def test_help_forwards_to_local_binary(tmp_path):
    h = _Harness()
    fake_proc = MagicMock()
    fake_proc.stdout.__iter__.return_value = iter(['Brutus help\n', 'options\n'])
    fake_proc.stderr.read.return_value = ''
    fake_proc.returncode = 0

    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch('praetorian_cli.runners.local.LocalRunner') as mock_cls:
        mock_cls.return_value.run_streaming.return_value = fake_proc
        h._cmd_run(['brutus', '--help'])

    # run_streaming should have been called with ['--help'].
    mock_cls.return_value.run_streaming.assert_called_once()
    call_args = mock_cls.return_value.run_streaming.call_args.args[0]
    assert call_args == ['--help']


def test_help_when_not_installed_prints_install_hint():
    h = _Harness()
    with patch('praetorian_cli.runners.local.is_installed', return_value=False):
        h._cmd_run(['brutus', '--help'])
    output = '\n'.join(h.console.lines)
    assert 'install' in output.lower()


def test_no_passthrough_uses_remote_path():
    """Back-compat: bare `run brutus <key>` still queues a remote job."""
    h = _Harness()
    # Force remote by claiming the binary is NOT installed.
    with patch('praetorian_cli.runners.local.is_installed', return_value=False), \
         patch.object(_Harness, '_try_queue_job', return_value=[{'key': '#job#x'}]) as mock_queue:
        h._cmd_run(['brutus', '#asset#10.0.1.5'])
    assert mock_queue.called
