"""Unit tests for console `run` passthrough and local execution path."""
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.ui.console.commands.tools import ToolCommands
from praetorian_cli.sdk.test.ui_mocks import MockConsole as _BaseMockConsole

pytestmark = pytest.mark.tui


class MockConsole(_BaseMockConsole):
    """Console mock that tolerates Rich kwargs like markup=/highlight=."""

    def print(self, msg="", **kwargs):
        self.lines.append(str(msg))


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


def test_run_tool_locally_streams_and_uploads(tmp_path, monkeypatch):
    """Direct exercise of _run_tool_locally body: streaming + Guard upload."""
    h = _Harness()

    fake_proc = MagicMock()
    fake_proc.stdout.__iter__.return_value = iter([
        'scan start\n', '[+] success\n', 'scan done\n',
    ])
    fake_proc.stderr.read.return_value = ''
    fake_proc.returncode = 0

    fake_runner = MagicMock()
    fake_runner.run_streaming.return_value = fake_proc

    fake_plugin = MagicMock()
    fake_plugin.build_args.return_value = ['--target', 'example.com', '--protocol', 'ssh']

    with patch('praetorian_cli.runners.local.LocalRunner', return_value=fake_runner), \
         patch('praetorian_cli.runners.local.get_tool_plugin', return_value=fake_plugin):
        h._run_tool_locally('brutus', '#asset#example.com', ['--protocol', 'ssh'])

    # Plugin was consulted with the stripped target + pass_through.
    fake_plugin.build_args.assert_called_once()
    call_kwargs = fake_plugin.build_args.call_args.kwargs
    assert call_kwargs.get('pass_through') == ['--protocol', 'ssh']

    # LocalRunner was invoked with the plugin's argv.
    fake_runner.run_streaming.assert_called_once_with(
        ['--target', 'example.com', '--protocol', 'ssh'],
    )

    # Subprocess stdout made it to the console (markup-escaped so [+] doesn't crash Rich).
    output = '\n'.join(h.console.lines)
    assert 'scan start' in output
    assert '[+] success' in output
    assert 'scan done' in output

    # Guard upload was attempted.
    assert h.sdk.files.add.called
    guard_path_arg = h.sdk.files.add.call_args.args[1]
    assert guard_path_arg.startswith('proofs/local/brutus/')


def test_run_tool_locally_timeout_sets_exit_code(monkeypatch):
    """When the subprocess times out, the post-kill wait sets a real returncode."""
    import subprocess
    h = _Harness()

    fake_proc = MagicMock()
    fake_proc.stdout.__iter__.return_value = iter(['partial\n'])
    # First .wait raises TimeoutExpired; the second (after kill) succeeds.
    fake_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd='brutus', timeout=600), None]
    fake_proc.stderr.read.return_value = ''
    fake_proc.returncode = -9

    fake_runner = MagicMock()
    fake_runner.run_streaming.return_value = fake_proc

    fake_plugin = MagicMock()
    fake_plugin.build_args.return_value = ['--target', 'x']

    with patch('praetorian_cli.runners.local.LocalRunner', return_value=fake_runner), \
         patch('praetorian_cli.runners.local.get_tool_plugin', return_value=fake_plugin):
        h._run_tool_locally('brutus', 'x', [])

    fake_proc.kill.assert_called_once()
    # The post-kill wait must have been called to reap the process.
    assert fake_proc.wait.call_count >= 2
    output = '\n'.join(h.console.lines)
    assert 'Timed out' in output
    assert 'Exit code: -9' in output  # NOT 'Exit code: None'
