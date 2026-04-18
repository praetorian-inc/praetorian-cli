"""Unit tests for `guard run tool` argument passthrough and errors."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    """Build a minimal fake SDK covering the calls `guard run tool` makes."""
    sdk = MagicMock()
    sdk.capabilities.list.return_value = [
        {'name': 'brutus', 'target': ['asset'], 'description': 'creds', 'executor': 'chariot'},
    ]
    sdk.search.fulltext.return_value = ([{'key': '#asset#10.0.1.5', 'dns': '10.0.1.5'}], None)
    sdk.jobs.add.return_value = [{'key': '#job#abc'}]
    return sdk


def _invoke(runner, fake_sdk, argv):
    """Invoke the CLI with a patched SDK factory.

    The `chariot` click group replaces `ctx.obj` with a `Chariot` instance,
    built lazily inside the group callback via `from praetorian_cli.sdk.chariot
    import Chariot`. We patch that source symbol so every instantiation yields
    our fake SDK. We also seed `ctx.obj` with the dict shape the group expects
    (`{'keychain', 'proxy'}`) so invocation doesn't blow up before the patch
    takes effect.
    """
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, catch_exceptions=False)


def test_passthrough_collects_unknown_options(runner, fake_sdk):
    """Unknown options after target flow into tool_args and reach the local plugin."""
    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch('praetorian_cli.handlers.run._run_local') as mock_local:
        _invoke(runner, fake_sdk, [
            'run', 'tool', 'brutus', '10.0.1.5:22',
            '--protocol', 'ssh', '-U', 'users.txt',
        ])
    assert mock_local.called
    kwargs = mock_local.call_args.kwargs or {}
    # The fifth positional is either pass_through or tool_args depending on our impl;
    # we assert on the call_args tuple directly.
    pass_through = mock_local.call_args.args[-1]
    assert list(pass_through) == ['--protocol', 'ssh', '-U', 'users.txt']


def test_double_dash_separator_forwards_own_flag_collisions(runner, fake_sdk):
    """Flags that collide with our own names (e.g. --wait) still pass through after `--`."""
    with patch('praetorian_cli.runners.local.is_installed', return_value=True), \
         patch('praetorian_cli.handlers.run._run_local') as mock_local:
        result = _invoke(runner, fake_sdk, [
            'run', 'tool', 'brutus', '10.0.1.5:22', '--', '--wait', '--foo',
        ])
    assert result.exit_code == 0
    pass_through = mock_local.call_args.args[-1]
    assert list(pass_through) == ['--wait', '--foo']


def test_passthrough_with_remote_errors(runner, fake_sdk):
    """Extra args are local-only — remote execution must reject them."""
    result = _invoke(runner, fake_sdk, [
        'run', 'tool', 'brutus', '10.0.1.5:22', '--remote',
        '--protocol', 'ssh',
    ])
    assert result.exit_code != 0
    assert 'local' in result.output.lower()


def test_passthrough_with_ask_errors(runner, fake_sdk):
    """Extra args can't route through Marcus (agent path)."""
    result = _invoke(runner, fake_sdk, [
        'run', 'tool', 'brutus', '10.0.1.5:22', '--ask',
        '--protocol', 'ssh',
    ])
    assert result.exit_code != 0
    assert 'local' in result.output.lower() or 'agent' in result.output.lower()


def test_no_passthrough_preserves_remote_path(runner, fake_sdk):
    """No trailing args and --remote: existing direct-job path still works."""
    with patch('praetorian_cli.handlers.run._run_direct') as mock_direct:
        result = _invoke(runner, fake_sdk, [
            'run', 'tool', 'brutus', '10.0.1.5', '--remote',
        ])
    assert result.exit_code == 0
    assert mock_direct.called


def test_local_and_remote_conflict(runner, fake_sdk):
    """--local + --remote is always a user error."""
    result = _invoke(runner, fake_sdk, [
        'run', 'tool', 'brutus', '10.0.1.5', '--local', '--remote',
    ])
    assert result.exit_code != 0
    assert '--local' in result.output
    assert '--remote' in result.output


def test_local_and_ask_conflict(runner, fake_sdk):
    """--local + --ask is always a user error."""
    result = _invoke(runner, fake_sdk, [
        'run', 'tool', 'brutus', '10.0.1.5', '--local', '--ask',
    ])
    assert result.exit_code != 0
    assert '--local' in result.output
    assert '--ask' in result.output


def test_remote_and_ask_conflict(runner, fake_sdk):
    """--remote + --ask is always a user error."""
    result = _invoke(runner, fake_sdk, [
        'run', 'tool', 'brutus', '10.0.1.5', '--remote', '--ask',
    ])
    assert result.exit_code != 0
    assert '--remote' in result.output
    assert '--ask' in result.output
