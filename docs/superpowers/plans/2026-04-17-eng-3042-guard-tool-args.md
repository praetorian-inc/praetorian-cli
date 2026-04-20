# ENG-3042 — Guard tool argument handling implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken argument handling for `guard run tool <tool> <target> [extras]` (CLI) and `run <tool> <target> [extras]` (console) so operators can pass tool-specific flags (like Brutus's `-U users.txt --protocol ssh`), and fix `BrutusPlugin` emitting the wrong target flag.

**Architecture:** Two-layer fix. (1) `runners/local.py` — correct `BrutusPlugin` to emit `--target`/`--protocol` and thread a `pass_through` list through every plugin so caller-supplied flags reach the binary. (2) `handlers/run.py` and `ui/console/commands/tools.py` — collect unknown trailing options plus `--`-separated args, forward them to local plugins, and refuse combinations that don't make sense (`--remote`, `--ask`).

**Spec:** `docs/superpowers/specs/2026-04-17-eng-3042-guard-tool-args-design.md`

**Tech Stack:** Python, Click, pytest, prompt_toolkit + Rich (console)

---

### File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `praetorian_cli/runners/local.py` | Add `_infer_protocol`, `_has_flag` helpers; fix `BrutusPlugin`; thread `pass_through` through base + all plugins |
| Modify | `praetorian_cli/handlers/run.py` | `guard run tool` accepts `tool_args` via `nargs=-1 UNPROCESSED` + `ignore_unknown_options`; forwards to `_run_local`; errors on `--remote` / `--ask` + passthrough |
| Modify | `praetorian_cli/ui/console/commands/tools.py` | `_cmd_run` splits own flags from pass-through; adds local execution path (reusing `LocalRunner`); `run <tool> --help` forwards to binary |
| Modify | `docs/console.md` | Document passthrough usage in console docs |
| Create | `praetorian_cli/sdk/test/test_local_runner.py` | Unit tests for `BrutusPlugin._build`, `_infer_protocol`, `_has_flag`, base plugin pass_through |
| Create | `praetorian_cli/sdk/test/test_run_cli.py` | CLI tests for `guard run tool` passthrough via `CliRunner` |
| Create | `praetorian_cli/sdk/test/ui/test_console_tools.py` | Console `_cmd_run` tests for passthrough & local exec |

---

## Task 1 — Helpers: `_infer_protocol` and `_has_flag`

**Files:**
- Modify: `praetorian_cli/runners/local.py`
- Create: `praetorian_cli/sdk/test/test_local_runner.py`

- [ ] **Step 1: Write failing tests for `_infer_protocol` and `_has_flag`**

Create `praetorian_cli/sdk/test/test_local_runner.py`:

```python
import pytest

from praetorian_cli.runners.local import _infer_protocol, _has_flag


class TestInferProtocol:
    def test_ssh_port(self):
        assert _infer_protocol('10.0.1.5:22') == 'ssh'

    def test_rdp_port(self):
        assert _infer_protocol('host.example.com:3389') == 'rdp'

    def test_ftp_port(self):
        assert _infer_protocol('192.168.1.1:21') == 'ftp'

    def test_smb_port(self):
        assert _infer_protocol('10.0.0.5:445') == 'smb'

    def test_telnet_port(self):
        assert _infer_protocol('10.0.0.5:23') == 'telnet'

    def test_mysql_port(self):
        assert _infer_protocol('db.example.com:3306') == 'mysql'

    def test_postgres_port(self):
        assert _infer_protocol('db.example.com:5432') == 'postgres'

    def test_unknown_port_returns_none(self):
        assert _infer_protocol('host:9999') is None

    def test_no_port_returns_none(self):
        assert _infer_protocol('example.com') is None

    def test_malformed_port_returns_none(self):
        assert _infer_protocol('host:notaport') is None

    def test_ipv6_bracket_form(self):
        # IPv6 addresses use [::1]:22 bracket form — we don't need to support this,
        # just not crash on it.
        assert _infer_protocol('[::1]:22') in ('ssh', None)


class TestHasFlag:
    def test_empty_passthrough(self):
        assert _has_flag(None, '-u') is False
        assert _has_flag([], '-u') is False

    def test_single_flag_present(self):
        assert _has_flag(['-u', 'foo'], '-u') is True

    def test_any_of_multiple(self):
        assert _has_flag(['-U', 'users.txt'], '-u', '-U') is True
        assert _has_flag(['-u', 'foo'], '-u', '-U') is True

    def test_flag_absent(self):
        assert _has_flag(['--other', 'val'], '-u') is False

    def test_flag_as_value_ignored(self):
        # A flag appearing only as a value to another flag should not match.
        # Simpler: we match anywhere in the list. This keeps the helper small.
        # If a user's file path happens to be '-u', that's their problem.
        assert _has_flag(['--config', '-u'], '-u') is True
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests fail with `ImportError: cannot import name '_infer_protocol'` (or similar).

- [ ] **Step 3: Implement `_infer_protocol` and `_has_flag`**

Open `praetorian_cli/runners/local.py` and add, after the `INSTALLABLE_TOOLS` dict (before `_detect_platform`):

```python
# Well-known service ports for Brutus protocol auto-detection.
# Keep this minimal: only protocols Brutus natively supports.
_WELL_KNOWN_PORTS = {
    22: 'ssh',
    3389: 'rdp',
    21: 'ftp',
    445: 'smb',
    23: 'telnet',
    3306: 'mysql',
    5432: 'postgres',
}


def _infer_protocol(target: str):
    """Infer protocol from a 'host:port' target using well-known ports.

    Returns the protocol name or None if no inference is possible.
    """
    if not target or ':' not in target:
        return None
    # rsplit so 'host:port' works even if host contains ':'
    _, sep, port_str = target.rpartition(':')
    if not sep:
        return None
    try:
        port = int(port_str)
    except ValueError:
        return None
    return _WELL_KNOWN_PORTS.get(port)


def _has_flag(pass_through, *flags):
    """Return True if any of the given flag names appears in pass_through."""
    if not pass_through:
        return False
    flag_set = set(flags)
    return any(arg in flag_set for arg in pass_through)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/runners/local.py praetorian_cli/sdk/test/test_local_runner.py
git commit -m "feat: add _infer_protocol/_has_flag helpers for tool plugins"
```

---

## Task 2 — Thread `pass_through` through base `ToolPlugin`

**Files:**
- Modify: `praetorian_cli/runners/local.py`
- Modify: `praetorian_cli/sdk/test/test_local_runner.py`

- [ ] **Step 1: Write failing test for base plugin pass_through**

Append to `praetorian_cli/sdk/test/test_local_runner.py`:

```python
from praetorian_cli.runners.local import ToolPlugin


class TestToolPluginBase:
    def test_default_plugin_passes_through(self):
        plugin = ToolPlugin()
        args = plugin.build_args('example.com', pass_through=['--flag', 'val'])
        assert args == ['example.com', '--flag', 'val']

    def test_default_plugin_without_passthrough(self):
        plugin = ToolPlugin()
        assert plugin.build_args('example.com') == ['example.com']

    def test_default_plugin_with_json_config_and_passthrough(self):
        plugin = ToolPlugin()
        args = plugin.build_args('t', extra_config='{"k":"v"}', pass_through=['--x'])
        # Default plugin ignores config but appends pass_through.
        assert args == ['t', '--x']
```

- [ ] **Step 2: Run test and verify failure**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py::TestToolPluginBase -v`
Expected: TypeError about unexpected keyword `pass_through` or similar.

- [ ] **Step 3: Update base `ToolPlugin` to accept and forward `pass_through`**

In `praetorian_cli/runners/local.py`, replace the `ToolPlugin` class (around line 191-204) with:

```python
class ToolPlugin:
    """Base class for local tool argument builders."""

    def build_args(self, target, extra_config='', pass_through=None):
        config = {}
        if extra_config:
            try:
                config = json.loads(extra_config) if isinstance(extra_config, str) else extra_config
            except (json.JSONDecodeError, TypeError):
                pass
        args = self._build(target, config, pass_through=pass_through)
        return args

    def _build(self, target, config, pass_through=None):
        args = [target]
        if pass_through:
            args.extend(pass_through)
        return args
```

- [ ] **Step 4: Run the test and verify pass**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py::TestToolPluginBase -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/runners/local.py praetorian_cli/sdk/test/test_local_runner.py
git commit -m "feat: base ToolPlugin accepts pass_through kwarg"
```

---

## Task 3 — Fix `BrutusPlugin`

**Files:**
- Modify: `praetorian_cli/runners/local.py`
- Modify: `praetorian_cli/sdk/test/test_local_runner.py`

- [ ] **Step 1: Write failing tests for `BrutusPlugin`**

Append to `praetorian_cli/sdk/test/test_local_runner.py`:

```python
from praetorian_cli.runners.local import BrutusPlugin


class TestBrutusPlugin:
    def setup_method(self):
        self.plugin = BrutusPlugin()

    def test_bare_target_emits_target_flag(self):
        args = self.plugin.build_args('example.com')
        assert args == ['--target', 'example.com']

    def test_target_with_ssh_port_infers_protocol(self):
        args = self.plugin.build_args('10.0.1.5:22')
        assert args == ['--target', '10.0.1.5:22', '--protocol', 'ssh']

    def test_target_with_rdp_port_infers_protocol(self):
        args = self.plugin.build_args('host.example.com:3389')
        assert args == ['--target', 'host.example.com:3389', '--protocol', 'rdp']

    def test_unknown_port_does_not_infer_protocol(self):
        args = self.plugin.build_args('host:9999')
        assert args == ['--target', 'host:9999']

    def test_config_protocol_overrides_inference(self):
        args = self.plugin.build_args('10.0.1.5:22', extra_config='{"protocol":"smb"}')
        assert '--protocol' in args
        idx = args.index('--protocol')
        assert args[idx + 1] == 'smb'

    def test_config_usernames_and_passwords(self):
        args = self.plugin.build_args(
            'host:22',
            extra_config='{"usernames":"root,admin","passwords":"pw1,pw2"}',
        )
        assert args == [
            '--target', 'host:22', '--protocol', 'ssh',
            '-u', 'root,admin', '-p', 'pw1,pw2',
        ]

    def test_passthrough_appended(self):
        args = self.plugin.build_args('host:22', pass_through=['--spray', '-v'])
        assert args == ['--target', 'host:22', '--protocol', 'ssh', '--spray', '-v']

    def test_passthrough_username_file_suppresses_structured_u(self):
        # Caller-supplied -U wins — we should not also emit structured -u.
        args = self.plugin.build_args(
            'host:22',
            extra_config='{"usernames":"root,admin"}',
            pass_through=['-U', 'users.txt'],
        )
        # '-u' (structured) must NOT be present; '-U' must be.
        assert '-u' not in args
        assert '-U' in args
        assert args[args.index('-U') + 1] == 'users.txt'

    def test_passthrough_protocol_suppresses_inference(self):
        args = self.plugin.build_args(
            'host:22',
            pass_through=['--protocol', 'rdp'],
        )
        # Only one --protocol, and it's the passthrough value.
        assert args.count('--protocol') == 1
        assert args[args.index('--protocol') + 1] == 'rdp'

    def test_passthrough_password_file_suppresses_structured_p(self):
        args = self.plugin.build_args(
            'host:22',
            extra_config='{"passwords":"pw"}',
            pass_through=['-P', 'passes.txt'],
        )
        assert '-p' not in args
        assert '-P' in args
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py::TestBrutusPlugin -v`
Expected: Failures — current plugin emits `-t target`, not `--target target`, and doesn't support pass_through.

- [ ] **Step 3: Replace `BrutusPlugin._build`**

In `praetorian_cli/runners/local.py`, find the `BrutusPlugin` class (around line 207-214) and replace it with:

```python
class BrutusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['--target', target]

        # Protocol: explicit config > caller passthrough wins silently > inferred
        caller_has_protocol = _has_flag(pass_through, '--protocol')
        if not caller_has_protocol:
            proto = config.get('protocol') or _infer_protocol(target)
            if proto:
                args.extend(['--protocol', proto])

        if config.get('usernames') and not _has_flag(pass_through, '-u', '-U'):
            args.extend(['-u', config['usernames']])
        if config.get('passwords') and not _has_flag(pass_through, '-p', '-P'):
            args.extend(['-p', config['passwords']])

        if pass_through:
            args.extend(pass_through)
        return args
```

- [ ] **Step 4: Run the tests and verify pass**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py::TestBrutusPlugin -v`
Expected: All 10 tests pass.

- [ ] **Step 5: Run the full `test_local_runner.py` suite to catch regressions**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add praetorian_cli/runners/local.py praetorian_cli/sdk/test/test_local_runner.py
git commit -m "fix(brutus): emit --target/--protocol and accept passthrough flags"
```

---

## Task 4 — Propagate `pass_through` to the remaining plugins

**Files:**
- Modify: `praetorian_cli/runners/local.py`
- Modify: `praetorian_cli/sdk/test/test_local_runner.py`

These plugins already exist and all must accept (and forward) `pass_through` so callers can always tack on flags regardless of tool.

- [ ] **Step 1: Write failing tests for each plugin's passthrough behavior**

Append to `praetorian_cli/sdk/test/test_local_runner.py`:

```python
from praetorian_cli.runners.local import (
    NucleiPlugin, TitusPlugin, TrajanPlugin, JuliusPlugin, AugustusPlugin,
    NervaPlugin, GatoPlugin, UrlTargetPlugin, ScanTargetPlugin,
)


class TestPluginsForwardPassthrough:
    """Every plugin must append pass_through args last."""

    @pytest.mark.parametrize('plugin_cls,expected_prefix', [
        (NucleiPlugin, ['-u', 'example.com', '-jsonl']),
        (TitusPlugin, ['scan', 'example.com']),
        (TrajanPlugin, ['scan', 'example.com']),
        (JuliusPlugin, ['-t', 'example.com']),
        (AugustusPlugin, ['scan', '-t', 'example.com']),
        (NervaPlugin, ['-t', 'example.com']),
        (GatoPlugin, ['enumerate', '-t', 'example.com']),
        (UrlTargetPlugin, ['scan', '-u', 'example.com']),
        (ScanTargetPlugin, ['scan', 'example.com']),
    ])
    def test_plugin_appends_passthrough(self, plugin_cls, expected_prefix):
        plugin = plugin_cls()
        args = plugin.build_args('example.com', pass_through=['--debug', '-v'])
        assert args[:len(expected_prefix)] == expected_prefix
        assert args[-2:] == ['--debug', '-v']

    def test_plugin_no_passthrough_unchanged(self):
        # Regression guard for the default (no passthrough) path.
        assert NucleiPlugin().build_args('example.com') == ['-u', 'example.com', '-jsonl']
        assert TitusPlugin().build_args('x') == ['scan', 'x']
        assert JuliusPlugin().build_args('x') == ['-t', 'x']
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py::TestPluginsForwardPassthrough -v`
Expected: Fails — plugins' `_build` signatures don't accept `pass_through`.

- [ ] **Step 3: Update each plugin's `_build` signature**

In `praetorian_cli/runners/local.py`, replace each of the following classes' `_build` methods. Keep all other methods untouched. Every `_build` now takes `pass_through=None` and appends it last.

```python
class NucleiPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-u', target, '-jsonl']
        if config.get('templates'):
            args.extend(['-t', config['templates']])
        if pass_through:
            args.extend(pass_through)
        return args


class TitusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if config.get('validation') == 'true':
            args.append('--validate')
        if pass_through:
            args.extend(pass_through)
        return args


class TrajanPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if config.get('token'):
            args.extend(['--token', config['token']])
        if pass_through:
            args.extend(pass_through)
        return args


class JuliusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class AugustusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', '-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class NervaPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class GatoPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['enumerate', '-t', target]
        if config.get('token'):
            args.extend(['--token', config['token']])
        if pass_through:
            args.extend(pass_through)
        return args


class UrlTargetPlugin(ToolPlugin):
    """For tools that take scan -u <target>."""
    def _build(self, target, config, pass_through=None):
        args = ['scan', '-u', target]
        if pass_through:
            args.extend(pass_through)
        return args


class ScanTargetPlugin(ToolPlugin):
    """For tools that take scan <target>."""
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if pass_through:
            args.extend(pass_through)
        return args
```

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/runners/local.py praetorian_cli/sdk/test/test_local_runner.py
git commit -m "feat: thread pass_through through all local tool plugins"
```

---

## Task 5 — Wire `tool_args` into the CLI `guard run tool` command

**Files:**
- Modify: `praetorian_cli/handlers/run.py`
- Create: `praetorian_cli/sdk/test/test_run_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `praetorian_cli/sdk/test/test_run_cli.py`:

```python
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
    """Invoke the CLI with a patched SDK factory."""
    with patch('praetorian_cli.handlers.cli_decorators.Chariot', return_value=fake_sdk):
        return runner.invoke(chariot, argv, catch_exceptions=False)


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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest praetorian_cli/sdk/test/test_run_cli.py -v`
Expected: Fails — Click rejects `-U` / `--protocol` as unknown options; `--remote + extras` check doesn't exist.

- [ ] **Step 3: Update the `tool` command to accept `tool_args`**

In `praetorian_cli/handlers/run.py`, replace the `@run.command('tool')` decorator block (currently at lines 127-173) with:

```python
@run.command(
    'tool',
    context_settings={'ignore_unknown_options': True, 'allow_extra_args': True},
)
@cli_handler
@click.argument('tool_name')
@click.argument('target')
@click.argument('tool_args', nargs=-1, type=click.UNPROCESSED)
@click.option('-c', '--config', 'extra_config', default='', help='Extra JSON config to merge')
@click.option('--credential', multiple=True, help='Credential ID(s) to use')
@click.option('--wait', is_flag=True, default=False, help='Wait for job completion and show results')
@click.option('--ask', 'use_agent', is_flag=True, default=False, help='Run via Marcus AI agent instead of direct job')
@click.option('--local', is_flag=True, default=False, help='Run locally using installed binary')
@click.option('--remote', is_flag=True, default=False, help='Force remote job execution on Guard backend')
def tool(sdk, tool_name, target, tool_args, extra_config, credential, wait, use_agent, local, remote):
    """ Execute a named security tool against a target

    By default, runs LOCALLY if the binary is installed, otherwise schedules
    a remote job. Use --local or --remote to force. Any additional arguments
    after the target are forwarded to the local binary. Use `--` to pass
    flags that collide with our own options.

    \b
    Example usages:
        guard run tool brutus 10.0.1.5:22
        guard run tool brutus 10.0.1.5:22 --protocol ssh -U users.txt
        guard run tool brutus 10.0.1.5:22 -- --wait
        guard run tool nuclei example.com --remote -c '{"templates":"cves/"}'
    """
    from praetorian_cli.runners.local import is_installed as _is_installed

    cap = resolve_capability(sdk, tool_name.lower())
    if not cap:
        error(f'Unknown capability: {tool_name}. Use "guard run capabilities" to see available capabilities.')

    tool_args = list(tool_args or [])

    # Decide local vs remote first so we can validate tool_args against the resolved path.
    run_local = local or (not remote and not use_agent and _is_installed(tool_name.lower()))

    if tool_args and (remote or use_agent or not run_local):
        error(
            'Extra arguments after the target are only supported when running locally. '
            'Install the tool locally ("guard run install %s") or encode settings as JSON '
            'via -c \'{"key":"value"}\'.' % tool_name.lower()
        )

    if run_local:
        _run_local(sdk, tool_name.lower(), target, extra_config, tool_args)
    elif use_agent:
        target_key, warning = resolve_target(sdk, target, cap['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_via_agent(sdk, cap, target_key)
    else:
        target_key, warning = resolve_target(sdk, target, cap['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_direct(sdk, cap, target_key, extra_config, list(credential), wait)
```

- [ ] **Step 4: Update `_run_local` to accept and forward `tool_args`**

In the same file (`praetorian_cli/handlers/run.py`), update `_run_local` (currently at lines 379-433):

Change signature from:
```python
def _run_local(sdk, tool_name, target, extra_config):
```
to:
```python
def _run_local(sdk, tool_name, target, extra_config, tool_args=None):
```

Inside the function, change the `plugin.build_args` call (line 395) from:
```python
    args = plugin.build_args(raw_target, extra_config)
```
to:
```python
    args = plugin.build_args(raw_target, extra_config, pass_through=list(tool_args or []))
```

Leave the rest of `_run_local` untouched.

- [ ] **Step 5: Run CLI tests and verify pass**

Run: `pytest praetorian_cli/sdk/test/test_run_cli.py -v`
Expected: All 5 tests pass.

- [ ] **Step 6: Run the full local-runner test file (regression check)**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests still pass.

- [ ] **Step 7: Commit**

```bash
git add praetorian_cli/handlers/run.py praetorian_cli/sdk/test/test_run_cli.py
git commit -m "feat(run): forward trailing args to local tool binaries"
```

---

## Task 6 — Add local execution path + passthrough to console `run`

**Files:**
- Modify: `praetorian_cli/ui/console/commands/tools.py`
- Create: `praetorian_cli/sdk/test/ui/test_console_tools.py`

The console currently only queues remote jobs or routes to Marcus. For the passthrough story to work it needs a local execution path (reusing the CLI's `LocalRunner`). Local execution kicks in only when (a) the binary is installed AND (b) the user passed extras, OR (c) the user explicitly asked with `--local`.

- [ ] **Step 1: Write failing tests for `_cmd_run` passthrough**

Create `praetorian_cli/sdk/test/ui/test_console_tools.py`:

```python
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
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_tools.py -v`
Expected: Failures — `_run_tool_locally` does not exist; `--` handling / `--help` passthrough don't exist.

- [ ] **Step 3: Update `_cmd_run` to split own flags from passthrough and route**

In `praetorian_cli/ui/console/commands/tools.py`, replace the entire `_cmd_run` method (starting around line 41, ending around line 118) with:

```python
    def _cmd_run(self, args):
        """Run a named security tool against a target, or execute active tool."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        from praetorian_cli.runners.local import is_installed as _is_installed

        if not args and self.context.active_tool:
            self._cmd_execute([])
            return
        if not args:
            self._print_tool_catalog(TOOL_ALIASES)
            return

        tool_name = args[0].lower()
        alias = TOOL_ALIASES.get(tool_name)
        if not alias:
            available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
            self.console.print(f'[error]Unknown tool: {tool_name}. Available: {available}[/error]')
            return

        rest = args[1:]

        # `run <tool> --help` — forward to local binary if installed.
        if rest and rest[0] == '--help':
            self._print_tool_help(tool_name)
            return

        if not rest:
            self.console.print(f'[dim]Usage: {tool_name} <target_key> [--ask] [--wait] [-- <tool-args>...][/dim]')
            self.console.print(f'[dim]  Target type: {alias["target_type"]}[/dim]')
            self.console.print(f'[dim]  {alias["description"]}[/dim]')
            return

        raw_target = rest[0]
        remaining = rest[1:]

        # Split own flags from passthrough. Honor `--` as an explicit boundary:
        # everything after `--` is passthrough, even if it collides with `--wait`/`--ask`.
        OWN_FLAGS = {'--ask', '--wait'}
        pass_through = []
        own = []
        if '--' in remaining:
            idx = remaining.index('--')
            own = remaining[:idx]
            pass_through = remaining[idx + 1:]
        else:
            for a in remaining:
                if a in OWN_FLAGS:
                    own.append(a)
                else:
                    pass_through.append(a)

        use_agent = '--ask' in own
        wait = '--wait' in own

        if pass_through and use_agent:
            self.console.print(
                '[error]Extra arguments are not supported with --ask (agent path). '
                'Drop --ask or use structured config.[/error]'
            )
            return

        if pass_through:
            if not _is_installed(tool_name):
                self.console.print(
                    f'[error]Extra arguments require the {tool_name} binary to be installed locally. '
                    f'Run "install {tool_name}" first.[/error]'
                )
                return
            self._run_tool_locally(tool_name, raw_target, pass_through)
            return

        # No passthrough — existing remote/agent flow.
        from praetorian_cli.handlers.run import resolve_target
        target_key, warning = resolve_target(self.sdk, raw_target, alias['target_type'])
        if not target_key:
            self.console.print(f'[error]{warning}[/error]')
            return
        if warning:
            self.console.print(f'[warning]{warning}[/warning]')

        capability = alias.get('capability')
        config = dict(alias.get('default_config', {}))

        if alias.get('agent') and (use_agent or not capability):
            agent_name = alias['agent']
            task_desc = f'Run {capability} against {target_key} and analyze the results.' if capability else f'Analyze {target_key} thoroughly.'
            message = self.context.apply_scope_to_message(task_desc)
            self.console.print(f'[info]Delegating to {agent_name} via Marcus...[/info]')
            response_text = self._send_to_marcus(message)
            if response_text:
                from rich.markdown import Markdown
                self.console.print(Markdown(response_text))
        else:
            import json
            config_str = json.dumps(config) if config else None
            result = self._try_queue_job(target_key, capability, config_str)
            if result is None:
                return
            if wait:
                self._wait_for_job(target_key, capability)

    def _print_tool_catalog(self, TOOL_ALIASES):
        """Render the agents/capabilities catalog shown when `run` is called bare."""
        agents = {k: v for k, v in TOOL_ALIASES.items() if v.get('agent') and k != 'secrets'}
        table = Table(title='Agents', border_style=self.colors['primary'])
        table.add_column('Agent', style=f'bold {self.colors["primary"]}', min_width=16)
        table.add_column('Description')
        for name, info in sorted(agents.items()):
            table.add_row(name, info['description'])
        self.console.print(table)

        caps = {k: v for k, v in TOOL_ALIASES.items() if not v.get('agent') and k != 'secrets'}
        if caps:
            table2 = Table(title='Capabilities', border_style=self.colors['dim'])
            table2.add_column('Capability', style=f'bold {self.colors["primary"]}', min_width=16)
            table2.add_column('Target', style=self.colors['accent'])
            table2.add_column('Description')
            for name, info in sorted(caps.items()):
                table2.add_row(name, info['target_type'], info['description'])
            self.console.print(table2)

        self.console.print(f'\n[dim]Usage: use <name> or <name> <target_key>[/dim]')

    def _print_tool_help(self, tool_name):
        """Run `<tool> --help` locally and stream its output to the console."""
        from praetorian_cli.runners.local import is_installed as _is_installed, LocalRunner
        if not _is_installed(tool_name):
            self.console.print(
                f'[warning]{tool_name} is not installed locally. Run "install {tool_name}" first.[/warning]'
            )
            return
        try:
            runner = LocalRunner(tool_name)
            proc = runner.run_streaming(['--help'])
            for line in proc.stdout:
                self.console.print(line.rstrip('\n'))
            stderr = proc.stderr.read() if proc.stderr else ''
            if stderr:
                self.console.print(f'[dim]{stderr}[/dim]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _run_tool_locally(self, tool_name, raw_target, pass_through):
        """Run an installed tool binary locally from the console."""
        from praetorian_cli.runners.local import LocalRunner, get_tool_plugin

        # Strip Guard key prefix for the raw target (same logic as CLI _run_local).
        target = raw_target
        if raw_target.startswith('#'):
            parts = raw_target.split('#')
            target = parts[-1] if len(parts) > 3 else parts[2] if len(parts) > 2 else raw_target

        plugin = get_tool_plugin(tool_name)
        tool_argv = plugin.build_args(target, pass_through=list(pass_through or []))

        try:
            runner = LocalRunner(tool_name)
        except FileNotFoundError as e:
            self.console.print(f'[error]{e}[/error]')
            return

        self.console.print(f'[info]Running {tool_name} locally against {target}...[/info]')
        self.console.print(f'[dim]Command: {tool_name} {" ".join(tool_argv)}[/dim]')
        self.console.print('[dim]' + '─' * 60 + '[/dim]')

        import subprocess
        proc = runner.run_streaming(tool_argv)
        output_lines = []
        try:
            for line in proc.stdout:
                self.console.print(line.rstrip('\n'))
                output_lines.append(line)
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.console.print('[error]Timed out (10 min).[/error]')

        stderr = proc.stderr.read() if proc.stderr else ''
        if stderr:
            self.console.print(f'[dim]{stderr}[/dim]')

        self.console.print('[dim]' + '─' * 60 + '[/dim]')
        self.console.print(f'[dim]Exit code: {proc.returncode}[/dim]')

        # Best-effort upload to Guard (mirrors CLI behavior).
        output_text = ''.join(output_lines)
        if output_text.strip():
            try:
                import tempfile, os
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix=f'{tool_name}-') as f:
                    f.write(output_text)
                    tmp_path = f.name
                guard_path = f'proofs/local/{tool_name}/{target.replace("/", "_")}'
                self.sdk.files.add(tmp_path, guard_path)
                os.unlink(tmp_path)
                self.console.print(f'[success]Output uploaded to Guard: {guard_path}[/success]')
            except Exception as e:
                self.console.print(f'[warning]Failed to upload output: {e}[/warning]')
```

(Keep every other method in `ToolCommands` unchanged.)

- [ ] **Step 4: Run the console tests and verify pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_tools.py -v`
Expected: All 7 tests pass.

- [ ] **Step 5: Run the full unit-test scope (regression check)**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py praetorian_cli/sdk/test/test_run_cli.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add praetorian_cli/ui/console/commands/tools.py praetorian_cli/sdk/test/ui/test_console_tools.py
git commit -m "feat(console): add local exec path with tool-arg passthrough to run"
```

---

## Task 7 — Audit notes for remaining plugins

**Files:**
- Modify: `praetorian_cli/runners/local.py`

No behaviour change — this task adds short annotations that record which plugin argument shapes have been verified against the binary's real help output, so future confusion about flags like `-t` doesn't reproduce the Brutus bug.

- [ ] **Step 1: Add verification note above `TOOL_PLUGINS`**

In `praetorian_cli/runners/local.py`, directly above the `TOOL_PLUGINS = {` line (around line 276), add:

```python
# Plugin verification status:
# - brutus:      verified against brutus --help (ENG-3042)
# - nuclei:      -u is the documented URL flag — OK
# - julius/nerva/nero: use -t <target>; unverified against each binary's --help
# - titus/trajan/vespasian/constantine/caligula: `scan <target>` — unverified
# - augustus/gato: `scan -t <target>` / `enumerate -t <target>` — unverified
# - cato/florian/hadrian: `scan -u <target>` — unverified
# Users can always override via `guard run tool <tool> <target> -- <raw args>`.
```

- [ ] **Step 2: Verify no test regressions**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add praetorian_cli/runners/local.py
git commit -m "docs(runners): annotate tool plugin verification status"
```

---

## Task 8 — Update `docs/console.md` with passthrough example

**Files:**
- Modify: `docs/console.md`

- [ ] **Step 1: Read the current `run` section**

Open `docs/console.md` and find the section that documents the `run` command. If no dedicated section exists, scan for the first mention of `run` / `brutus` in the file.

- [ ] **Step 2: Add a subsection titled "Passing tool-specific flags"**

Insert after the existing `run` usage documentation:

```markdown
### Passing tool-specific flags

Any arguments after `<target>` that the console doesn't recognise are forwarded
verbatim to the local tool binary. Use `--` as an explicit separator if a flag
collides with a console-owned option (`--ask`, `--wait`).

    run brutus 10.0.1.5:22 --protocol ssh -U users.txt
    run brutus 10.0.1.5:22 -- --wait --spray       # forwards --wait to brutus

`run <tool> --help` runs the local binary's `--help` and streams the output
into the console. Extra arguments require the binary to be installed
(`install <tool>`) and are rejected for the Marcus agent path (`--ask`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/console.md
git commit -m "docs(console): document tool-arg passthrough and --help"
```

---

## Task 9 — End-to-end smoke check

This task is manual verification — no code change.

- [ ] **Step 1: Re-run the whole test scope**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py praetorian_cli/sdk/test/test_run_cli.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`
Expected: All pass.

- [ ] **Step 2: Hand-verify with the real Brutus binary (requires `~/.praetorian/bin/brutus`)**

Run (replace target with any SSH host you own or a local port):

```
praetorian-cli guard run tool brutus 127.0.0.1:2222 --protocol ssh -U /tmp/empty-users.txt
```

Expected: The command runs brutus with the correct flag order; no Click "no such option" errors; no Brutus "invalid threads" error.

- [ ] **Step 3: Hand-verify remote-rejection**

```
praetorian-cli guard run tool brutus 127.0.0.1:2222 --remote --protocol ssh
```

Expected: Error "Extra arguments after the target are only supported when running locally…"

- [ ] **Step 4: Hand-verify console `run brutus --help`**

Launch `praetorian-cli guard console`, then type:

```
run brutus --help
```

Expected: Brutus' own help is printed inside the console.
