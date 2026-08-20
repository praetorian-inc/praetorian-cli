"""Contract for the best-effort update advisory in `@cli_handler`.

Offline only: every test redirects `XDG_CACHE_HOME` at `tmp_path` and replaces
`requests.get`, so no test reaches pypi.org or the real user cache directory.
"""

import json
import os
import stat
from pathlib import Path
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.cli_decorators import UPDATE_CHECK_CACHE_TTL_SECONDS


UPDATE_URL = "https://pypi.org/pypi/praetorian-cli/json"
DISABLE_ENV = "PRAETORIAN_CLI_DISABLE_UPDATE_CHECK"
CHECKED_AT = 1_700_000_000.0

# The three lines the advisory prints when pypi is ahead of the local install.
ADVISORY_FRAGMENTS = (
    "A new version of praetorian-cli is available",
    "You are currently running",
    'pip install --upgrade praetorian-cli',
)


def _cache_path(cache_root: Path) -> Path:
    return cache_root / "praetorian-cli" / "update-check.json"


def _response(latest: str = "1.1.0") -> Mock:
    response = Mock()
    response.json.return_value = {"releases": {latest: {}}}
    return response


def _configure_update_check(monkeypatch, cache_root: Path, interactive: bool = True):
    """Pin every input the advisory reads: cache root, opt-out, clock, version, TTY.

    The TTY force is the load-bearing part. `CliRunner` replaces stderr with a
    non-tty buffer, so `_stderr_is_interactive()` returns False inside *any*
    `CliRunner.invoke` and the advisory returns at its first gate. Without this,
    every test below would pass because the check never ran -- including the two
    that assert the request is *not* made, which would then prove nothing at all.
    """
    import praetorian_cli.handlers.cli_decorators as decorators

    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    monkeypatch.setattr(decorators, "version", lambda _package: "1.0.0")
    monkeypatch.setattr(decorators.time, "time", lambda: CHECKED_AT)
    monkeypatch.setattr(decorators, "_stderr_is_interactive", lambda: interactive)
    return decorators


def _successful_command(events=None):
    from praetorian_cli.handlers.cli_decorators import cli_handler

    @click.command()
    @cli_handler
    def command(_sdk):
        if events is not None:
            events.append("command")
        return "done"

    return command


def test_update_check_runs_after_success(monkeypatch, tmp_path):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    events = []
    request = Mock(
        side_effect=lambda *args, **kwargs: (
            events.append("request"),
            _response(),
        )[1]
    )
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(events), obj=object())

    assert result.exit_code == 0
    assert events == ["command", "request"]


def test_update_check_skips_unsuccessful_command(monkeypatch, tmp_path):
    from praetorian_cli.handlers.cli_decorators import cli_handler

    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(side_effect=AssertionError("update request must not run"))
    monkeypatch.setattr(decorators.requests, "get", request)

    @click.command()
    @cli_handler
    def command(_sdk):
        raise click.ClickException("command failed")

    result = CliRunner().invoke(command, obj=object())

    assert result.exit_code == 1
    assert "command failed" in result.output
    request.assert_not_called()


def test_update_check_disabled_by_explicit_environment_switch(monkeypatch, tmp_path):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setenv(DISABLE_ENV, "1")
    request = Mock(side_effect=AssertionError("disabled update request must not run"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_not_called()


def test_update_check_uses_fresh_cached_result_without_network(monkeypatch, tmp_path):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": CHECKED_AT, "latest_version": "1.2.0"}),
        encoding="utf-8",
    )
    request = Mock(side_effect=AssertionError("fresh cache must avoid network"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert "A new version of praetorian-cli is available: 1.2.0" in result.output
    request.assert_not_called()


def test_update_check_refreshes_stale_cached_result_once_with_short_timeout(
    monkeypatch, tmp_path
):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": 0, "latest_version": "1.0.0"}),
        encoding="utf-8",
    )
    request = Mock(return_value=_response("1.3.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert json.loads(cache_path.read_text(encoding="utf-8"))["latest_version"] == "1.3.0"


def test_update_check_timeout_failure_is_fail_open(monkeypatch, tmp_path):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(side_effect=TimeoutError("version service unavailable"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_called_once_with(UPDATE_URL, timeout=2)


def test_update_check_privacy_request_excludes_command_context(monkeypatch, tmp_path):
    from praetorian_cli.handlers.cli_decorators import cli_handler

    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(return_value=_response())
    monkeypatch.setattr(decorators.requests, "get", request)

    @click.command()
    @click.argument("target")
    @click.option("--profile")
    @click.option("--account")
    @cli_handler
    def command(_sdk, target, profile, account):
        return target, profile, account

    sentinels = ["SECRET_TARGET", "SECRET_PROFILE", "SECRET_ACCOUNT"]
    result = CliRunner().invoke(
        command,
        [sentinels[0], "--profile", sentinels[1], "--account", sentinels[2]],
        obj=object(),
    )

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    request_repr = repr(request.call_args)
    assert all(sentinel not in request_repr for sentinel in sentinels)


def test_update_check_cached_payload_is_private_and_atomically_replaced(
    monkeypatch, tmp_path
):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(mode=0o755)
    cache_path.write_text("malformed", encoding="utf-8")
    cache_path.chmod(0o644)
    request = Mock(return_value=_response("1.4.0"))
    monkeypatch.setattr(decorators.requests, "get", request)
    real_replace = os.replace
    replacements = []

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", record_replace)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert len(replacements) == 1
    temporary_path, destination = replacements[0]
    assert destination == cache_path
    assert temporary_path.parent == cache_path.parent
    assert temporary_path != cache_path
    assert not temporary_path.exists()
    assert stat.S_IMODE(cache_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert set(payload) == {"checked_at", "latest_version"}
    assert isinstance(payload["checked_at"], (int, float))
    assert payload["latest_version"] == "1.4.0"


def test_update_check_malformed_cache_and_network_failure_preserve_success(
    monkeypatch, tmp_path
):
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text("not-json", encoding="utf-8")
    request = Mock(side_effect=OSError("offline"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_called_once_with(UPDATE_URL, timeout=2)


def test_update_check_skipped_when_stderr_is_not_interactive(monkeypatch, tmp_path):
    """The advisory never runs for a command whose stderr is not a terminal.

    ENG-6643's "never runs where it is inappropriate" criterion: a piped or
    redirected stderr (a script, a cron job, a `2>` capture) must get no network
    call and no cache file -- the advisory is for humans at a terminal only.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path, interactive=False)
    request = Mock(side_effect=AssertionError("non-interactive stderr must not check"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_not_called()
    # Not merely no *fresh* cache: the check returns before the cache path is
    # even computed, so nothing under XDG_CACHE_HOME is created or read.
    assert not _cache_path(tmp_path).exists()
    assert not _cache_path(tmp_path).parent.exists()


def test_update_check_future_timestamp_is_treated_as_stale(monkeypatch, tmp_path):
    """A `checked_at` in the future is stale, so a bad clock cannot pin an answer.

    One hour ahead is the mutant-killing value: it is *inside* the TTL window in
    absolute terms, so a freshness test written as `age < TTL` without the
    `0 <= age` lower bound would read this entry as fresh and serve it forever.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": CHECKED_AT + 3600, "latest_version": "9.9.9"}),
        encoding="utf-8",
    )
    assert 3600 < UPDATE_CHECK_CACHE_TTL_SECONDS
    request = Mock(return_value=_response("1.5.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    # The future-dated entry was neither served to the user nor left in place.
    assert "9.9.9" not in result.output
    assert "1.5.0" in result.output
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload == {"checked_at": CHECKED_AT, "latest_version": "1.5.0"}


def test_update_check_write_failure_leaves_no_temporary_file(monkeypatch, tmp_path):
    """A failed cache write is swallowed, and leaves no debris behind.

    `_write_update_check_cache` creates its temp file with `mkstemp` in the
    destination directory; the `finally: temp_path.unlink(missing_ok=True)` is
    what keeps a mid-write failure from accumulating a temp file per invocation
    in the user's cache directory.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    # Stale, so the network path runs and a write is attempted.
    original_bytes = json.dumps({"checked_at": 0, "latest_version": "1.0.0"}).encode()
    cache_path.write_bytes(original_bytes)
    request = Mock(return_value=_response("1.6.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    def failing_dump(*_args, **_kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(decorators.json, "dump", failing_dump)

    result = CliRunner().invoke(_successful_command(), obj=object())

    # Fail open: the write failure never reaches the user or the exit status.
    assert result.exit_code == 0
    assert result.exception is None
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    # No temp entry left in the destination directory, and the previous cache
    # file is byte-for-byte intact -- the aborted write replaced nothing.
    assert sorted(p.name for p in cache_path.parent.iterdir()) == [cache_path.name]
    assert cache_path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "remote_version",
    ["1.0.0", "0.9.0"],
    ids=["remote-equals-local", "remote-older-than-local"],
)
def test_update_check_advisory_is_silent_when_local_version_is_current(
    monkeypatch, tmp_path, remote_version
):
    """No advisory unless pypi is strictly ahead: `>`, not `!=` and not `>=`.

    The local version is pinned at 1.0.0, so an equal remote is the boundary case
    a `>=` comparison would get wrong, and an older remote is what a `!=`
    comparison would get wrong -- both would nag a user who is already current.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(return_value=_response(remote_version))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    # `output` is the interleaved stdout+stderr stream and the command itself
    # prints nothing, so total emptiness is assertable -- a stronger claim than
    # the absence of the three fragments alone.
    assert result.output == ""
    for fragment in ADVISORY_FRAGMENTS:
        assert fragment not in result.output
