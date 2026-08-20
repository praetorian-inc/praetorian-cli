"""Contract for the best-effort update advisory in `@cli_handler`.

Offline only: every test redirects `XDG_CACHE_HOME` at `tmp_path` and replaces
`requests.get`, so no test reaches pypi.org or the real user cache directory.

Three properties carry most of the weight here, because each of them was a real
defect that reached a release:

* the advisory is *throttled by the record of the attempt*, not by the record of
  a success -- so the count of `requests.get` calls, not the presence of a cache
  file, is what these tests assert,
* the interactivity gate reads BOTH stdout and stderr, so `guard ... | jq` (a
  piped stdout with stderr still a tty) is skipped,
* a group callback that is merely delegating to a subcommand does not advise --
  otherwise the advisory prints before the work the user asked for, and prints
  twice when that subcommand succeeds.
"""

import json
import os
import stat
from concurrent.futures import CancelledError
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.cli_decorators import UPDATE_CHECK_CACHE_TTL_SECONDS


UPDATE_URL = "https://pypi.org/pypi/praetorian-cli/json"
DISABLE_ENV = "PRAETORIAN_CLI_DISABLE_UPDATE_CHECK"
CHECKED_AT = 1_700_000_000.0
LOCAL_VERSION = "1.0.0"

# The three lines the advisory prints when pypi is ahead of the local install.
ADVISORY_FRAGMENTS = (
    "A new version of praetorian-cli is available",
    "You are currently running",
    'pip install --upgrade praetorian-cli',
)
# The one fragment that appears exactly once per advisory, so counting it counts
# advisories.
ADVISORY_LEAD = ADVISORY_FRAGMENTS[0]

# The 0700/0600 guarantees are POSIX mode bits. Windows has no equivalent, and
# `Path.chmod` there is close to a no-op -- so these are skipped rather than
# deleted, which would drop the guarantee on the platforms that do enforce it.
posix_modes_only = pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode bits are not enforced on this platform"
)


def _cache_path(cache_root: Path) -> Path:
    return cache_root / "praetorian-cli" / "update-check.json"


def _response(latest: str = "1.1.0", releases=None) -> Mock:
    """A PyPI payload whose `releases` block is a decoy for `info.version`.

    The default decoy carries a prerelease that outranks `info.version` and a key
    `packaging` cannot parse at all, so an implementation that ranks release keys
    instead of reading `info.version` either advertises the prerelease or raises
    `InvalidVersion` into the fail-open arm -- and every test that uses this
    fixture notices, not just the one that names the behaviour.
    """
    response = Mock()
    if releases is None:
        releases = ["0.9.0", latest, "9.9.9rc1", "not-a-version"]
    response.json.return_value = {
        "info": {"version": latest},
        "releases": {key: [] for key in releases},
    }
    return response


def _response_without_info() -> Mock:
    """The payload shape that raises `KeyError` inside `_fetch_latest_version`."""
    response = Mock()
    response.json.return_value = {"releases": {"9.9.9": []}}
    return response


def _error_response() -> Mock:
    """A 500 from pypi.org: a body that parses fine, behind a failing status.

    The body deliberately carries a plausible-looking version, so a
    `_fetch_latest_version` that skipped `raise_for_status()` would advertise an
    error page's contents as the latest release.
    """
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("500 Server Error")
    response.json.return_value = {"info": {"version": "9.9.9"}, "releases": {}}
    return response


def _configure_inputs(monkeypatch, cache_root: Path):
    """Pin every input except the interactivity gate: cache root, opt-out, clock, version.

    The environment variables the gate itself reads are cleared here too, so an
    ambient `CI=true` on a developer's shell cannot silently turn a positive
    assertion below into a vacuous one.
    """
    import praetorian_cli.handlers.cli_decorators as decorators

    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    for name in ("CI", "GITHUB_ACTIONS", "TERM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(decorators, "version", lambda _package: LOCAL_VERSION)
    monkeypatch.setattr(decorators.time, "time", lambda: CHECKED_AT)
    return decorators


def _configure_update_check(monkeypatch, cache_root: Path, interactive: bool = True):
    """`_configure_inputs`, plus a forced answer for the interactivity gate.

    The gate force is the load-bearing part, and it belongs in this shared helper
    rather than in each test. `_session_is_interactive()` requires BOTH
    `sys.stdout.isatty()` and `sys.stderr.isatty()`, and `CliRunner` replaces both
    with non-tty buffers -- so inside *any* `CliRunner.invoke` the real gate is
    closed and the advisory returns before it does anything. A helper that forced
    only one of the two streams would leave it closed and every positive assertion
    below would pass vacuously, including the ones asserting that a request is
    *not* made, which would then prove nothing at all. Replacing the whole
    predicate also means a future third condition cannot silently reopen that
    hole.

    The real predicate is not left untested by this: it has its own tests, which
    deliberately do not use this helper -- see
    `test_update_check_requires_both_streams_to_be_a_terminal` and
    `test_update_check_skipped_by_non_interactive_environment`.
    """
    decorators = _configure_inputs(monkeypatch, cache_root)
    monkeypatch.setattr(decorators, "_session_is_interactive", lambda: interactive)
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


def _group_with_leaf(events, leaf_fails=False):
    """A real Click group in the shape production uses, plus one subcommand.

    Mirrors `praetorian_cli/handlers/aegis.py`: `invoke_without_command=True` so
    the bare group runs an interactive default, `@cli_handler` on the group
    callback *and* on the leaf, and `@click.pass_context` so the callback can read
    `ctx.invoked_subcommand`. That decorator stack is what puts two
    `upgrade_check` wrappers on the path of a single `guard aegis list`.
    """
    from praetorian_cli.handlers.cli_decorators import cli_handler

    @click.group(invoke_without_command=True)
    @cli_handler
    @click.pass_context
    def group(ctx, _sdk):
        events.append("group")
        if ctx.invoked_subcommand is None:
            events.append("group-default")

    @group.command("leaf")
    @cli_handler
    def leaf(_sdk):
        events.append("leaf")
        if leaf_fails:
            raise click.ClickException("leaf failed")

    return group


class _Stream:
    """The one method `_session_is_interactive` calls on `sys.stdout`/`sys.stderr`."""

    def __init__(self, tty):
        self._tty = tty

    def isatty(self):
        if self._tty == "raise":
            raise ValueError("detached stream")
        return self._tty


class _SysShim:
    """Stands in for the `sys` module so a tty can be simulated in-process.

    `CliRunner` owns the real `sys.stdout`/`sys.stderr` for the duration of an
    `invoke`, and there is no way to make its buffers report `isatty() is True`.
    `_session_is_interactive` reads both streams off the module-global `sys`, so
    replacing that global is how the tty cases become reachable at all -- and it
    is what makes the *positive* case of these tests (a request IS made) real
    rather than an artefact of a closed gate.
    """

    def __init__(self, stdout_tty, stderr_tty):
        self.stdout = _Stream(stdout_tty)
        self.stderr = _Stream(stderr_tty)


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


@pytest.mark.parametrize(
    "value",
    ["1", "true", "TRUE", " yes ", "on"],
    ids=["one", "true", "upper-true", "padded-yes", "on"],
)
def test_update_check_opt_out_accepts_conventional_truthy_values(
    monkeypatch, tmp_path, value
):
    """This is a privacy opt-out, so it accepts what a user would plausibly export.

    A user who exports `=true` and still gets network requests has been silently
    overruled by a parsing detail. Case and surrounding whitespace are normalized
    for the same reason.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setenv(DISABLE_ENV, value)
    request = Mock(side_effect=AssertionError("opted-out update request must not run"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_not_called()
    # Opting out is not merely quiet: nothing is written under the cache root
    # either, because the check returns before the cache path is computed.
    assert not _cache_path(tmp_path).parent.exists()


@pytest.mark.parametrize(
    "value", ["0", "false", ""], ids=["zero", "false", "empty"]
)
def test_update_check_opt_out_ignores_values_that_do_not_mean_yes(
    monkeypatch, tmp_path, value
):
    """The complement of the case above: a falsy value must not disable anything.

    Without this, `="0"` reading as "set, therefore disabled" would silently
    switch the advisory off for every user who wrote the value out explicitly.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setenv(DISABLE_ENV, value)
    request = Mock(return_value=_response("1.2.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert "A new version of praetorian-cli is available: 1.2.0" in result.output


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


def test_update_check_reads_info_version_and_ignores_release_keys(monkeypatch, tmp_path):
    """`info.version` is PyPI's latest STABLE release; the `releases` keys are not.

    `max(Version(k) for k in releases)` ranks `2.0.0rc1` above `1.1.0`, so it would
    nag every user to "upgrade" to a release candidate; and one unparseable key
    (PyPI has them) raises `InvalidVersion` into the fail-open arm and silences the
    advisory entirely. This payload contains both hazards, and the assertion is
    that neither one is what gets advertised.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(
        return_value=_response(
            "1.1.0", releases=["1.1.0", "2.0.0rc1", "3.0.0.dev1", "not-a-version"]
        )
    )
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert "A new version of praetorian-cli is available: 1.1.0" in result.output
    assert "2.0.0rc1" not in result.output
    assert "3.0.0.dev1" not in result.output
    # The prerelease is not merely unadvertised, it is not cached either -- a
    # cached prerelease would be served on every subsequent invocation for a day.
    assert (
        json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))["latest_version"]
        == "1.1.0"
    )


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


def test_update_check_cached_payload_is_atomically_replaced_twice(monkeypatch, tmp_path):
    """A refresh replaces the cache file TWICE, and every replace is atomic.

    Two by design, not by accident: the first records the attempt *before* the
    request goes out (which is what throttles a failing refresh), the second
    records its result. Both go through `mkstemp` in the destination directory
    plus `os.replace`, so a reader never sees a partially written file, and
    neither leaves the temp entry behind.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text("malformed", encoding="utf-8")
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
    assert len(replacements) == 2
    for temporary_path, destination in replacements:
        assert destination == cache_path
        assert temporary_path.parent == cache_path.parent
        assert temporary_path != cache_path
        assert not temporary_path.exists()
    # No debris of any kind left beside the destination.
    assert sorted(p.name for p in cache_path.parent.iterdir()) == [cache_path.name]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert set(payload) == {"checked_at", "latest_version"}
    assert isinstance(payload["checked_at"], (int, float))
    assert payload["latest_version"] == "1.4.0"


@posix_modes_only
def test_update_check_cache_is_private_to_the_user(monkeypatch, tmp_path):
    """0700 directory, 0600 file -- and the directory mode is *repaired*, not assumed.

    The directory is pre-created world-readable, which is what a `mkdir` whose mode
    was masked by the user's umask leaves behind. The explicit `chmod` after the
    `mkdir` is the only thing that closes it, so this asserts the end state rather
    than the call.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(mode=0o755)
    request = Mock(return_value=_response("1.4.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert cache_path.exists()
    assert stat.S_IMODE(cache_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600


def test_update_check_records_the_attempt_before_making_the_request(
    monkeypatch, tmp_path
):
    """The throttle record is on disk *before* `requests.get` is entered.

    Asserted from inside the mocked `get`, because the ordering is the whole
    mechanism: a record written only after a successful response cannot throttle
    the failures -- a timeout, an HTTP error, an unparseable payload, or a cache
    directory that cannot be written -- which is how this reached pypi.org on
    every single invocation. The previous known version rides along in that first
    record, so a refresh that then fails keeps advertising what was already known.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": 0, "latest_version": "1.2.0"}),
        encoding="utf-8",
    )
    snapshots = []

    def snapshot_then_respond(*_args, **_kwargs):
        snapshots.append(json.loads(cache_path.read_text(encoding="utf-8")))
        return _response("1.4.0")

    request = Mock(side_effect=snapshot_then_respond)
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert snapshots == [{"checked_at": CHECKED_AT, "latest_version": "1.2.0"}]
    # And the second record lands afterwards, carrying the fetched answer.
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "checked_at": CHECKED_AT,
        "latest_version": "1.4.0",
    }


def test_update_check_network_failure_is_throttled_across_invocations(
    monkeypatch, tmp_path
):
    """An unreachable index is probed ONCE per TTL, not once per invocation.

    The assertion is the request count across three separate invocations, not the
    existence of a cache file: a cache written only on success leaves a file
    behind on the *next* success while still probing on every failure, which is
    exactly the defect this pins.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(side_effect=OSError("name or service not known"))
    monkeypatch.setattr(decorators.requests, "get", request)

    for _ in range(3):
        result = CliRunner().invoke(_successful_command(), obj=object())
        assert result.exit_code == 0
        assert result.exception is None
        assert ADVISORY_LEAD not in result.output

    assert request.call_count == 1
    assert json.loads(_cache_path(tmp_path).read_text(encoding="utf-8")) == {
        "checked_at": CHECKED_AT,
        "latest_version": None,
    }


@posix_modes_only
@pytest.mark.skipif(
    getattr(os, "geteuid", lambda: 1)() == 0, reason="root ignores directory permissions"
)
def test_update_check_unwritable_cache_directory_stays_off_the_network(
    monkeypatch, tmp_path
):
    """Where the cache cannot be created at all, ZERO requests are made -- ever.

    Not one per invocation, and not one-then-stop: an environment whose probe rate
    cannot be limited is one that must not be probed. The read-only parent is a
    read-only `$XDG_CACHE_HOME`, an immutable container image layer, or a cache
    directory owned by another user.
    """
    read_only_root = tmp_path / "read-only"
    read_only_root.mkdir(mode=0o500)
    decorators = _configure_update_check(monkeypatch, read_only_root)
    request = Mock(side_effect=AssertionError("unthrottleable environment must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    try:
        for _ in range(3):
            result = CliRunner().invoke(_successful_command(), obj=object())
            assert result.exit_code == 0
            assert result.exception is None

        request.assert_not_called()
        assert not _cache_path(read_only_root).parent.exists()
    finally:
        # Restore write permission so pytest's tmp_path cleanup can remove it.
        read_only_root.chmod(0o700)


def test_update_check_unwritable_cache_makes_no_request(monkeypatch, tmp_path):
    """A cache write that fails mid-way stops the refresh AND leaves no debris.

    Zero requests, not one: the write is the throttle, so a write that cannot
    complete is the signal to stay off the network. The `finally:
    temp_path.unlink(missing_ok=True)` is what keeps the failure from
    accumulating a `mkstemp` leftover in the user's cache directory on every
    invocation, and the previous cache file is left byte-for-byte intact because
    `os.replace` was never reached.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    # Stale, so the refresh branch is the one taken and a write is attempted.
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
    request.assert_not_called()
    assert sorted(p.name for p in cache_path.parent.iterdir()) == [cache_path.name]
    assert cache_path.read_bytes() == original_bytes


def test_update_check_survives_a_platform_without_os_fchmod(monkeypatch, tmp_path):
    """`os.fchmod` is POSIX-only, and the advisory must not depend on it.

    Windows is simulated rather than skipped, because a skip is what let this
    ship: an `os.fchmod` after `mkstemp` raised `AttributeError` there, the
    fail-open arm swallowed it, the cache was therefore never written, and the
    advisory hit pypi.org on every invocation while printing nothing at all.
    `mkstemp` already creates its file 0600 regardless of umask, so nothing is
    lost by not calling it.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.delattr(os, "fchmod", raising=False)
    assert not hasattr(os, "fchmod")
    request = Mock(return_value=_response("1.7.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    advisories = 0
    for _ in range(3):
        result = CliRunner().invoke(_successful_command(), obj=object())
        assert result.exit_code == 0
        assert result.exception is None
        advisories += result.output.count(ADVISORY_LEAD)

    # Every invocation advises (the first from the network, the rest from the
    # cache it wrote), and only the first one reaches the network.
    assert advisories == 3
    assert request.call_count == 1
    assert (
        json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))["latest_version"]
        == "1.7.0"
    )


@pytest.mark.parametrize(
    "failure",
    ["os-error", "runtime-error", "http-error", "payload-without-info"],
)
def test_update_check_failed_refresh_retains_the_previous_version(
    monkeypatch, tmp_path, failure
):
    """A refresh that fails keeps advertising the version already known.

    Every failure shape must behave identically, and each is a different arm of
    the fetch: an `OSError` and a `RuntimeError` out of the request itself, a
    non-2xx response (`raise_for_status`), and a payload whose `info` key is
    missing (a `KeyError` from inside `_fetch_latest_version`). In each case the
    exception is swallowed -- the command still succeeds and says nothing about it
    -- the stale `1.2.0` is retained rather than dropped (dropping it would
    silence a real, still-valid advisory for a full TTL every time pypi.org
    hiccuped), and `checked_at` still advances, so the failure is throttled just
    like a success.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": 0, "latest_version": "1.2.0"}),
        encoding="utf-8",
    )
    if failure == "os-error":
        request = Mock(side_effect=OSError("connection reset by peer"))
    elif failure == "runtime-error":
        request = Mock(side_effect=RuntimeError("connection pool exhausted"))
    elif failure == "http-error":
        request = Mock(return_value=_error_response())
    else:
        request = Mock(return_value=_response_without_info())
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert result.output.count(ADVISORY_LEAD) == 1
    assert "A new version of praetorian-cli is available: 1.2.0" in result.output
    # Nothing about the failure itself reaches the user.
    assert "9.9.9" not in result.output
    assert "Error" not in result.output
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "checked_at": CHECKED_AT,
        "latest_version": "1.2.0",
    }


def test_update_check_fresh_unparseable_entry_is_silent_until_the_ttl_expires(
    monkeypatch, tmp_path
):
    """An unparseable cached version throttles like any other record, then recovers.

    A record whose version cannot be parsed is still a record of an attempt, so it
    must not be treated as "no cache" -- that would probe on every invocation for
    as long as the bad entry survived. It costs one TTL of silence, and no more:
    once the entry ages out the refresh runs and the advisory returns.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": CHECKED_AT, "latest_version": "not-a-version"}),
        encoding="utf-8",
    )
    request = Mock(return_value=_response("1.8.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    inside_ttl = CliRunner().invoke(_successful_command(), obj=object())

    assert inside_ttl.exit_code == 0
    assert inside_ttl.exception is None
    assert inside_ttl.output == ""
    request.assert_not_called()

    # Age the entry past its TTL: the refresh now runs and the advisory recovers.
    expired = CHECKED_AT + UPDATE_CHECK_CACHE_TTL_SECONDS + 1
    monkeypatch.setattr(decorators.time, "time", lambda: expired)

    after_ttl = CliRunner().invoke(_successful_command(), obj=object())

    assert after_ttl.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert "A new version of praetorian-cli is available: 1.8.0" in after_ttl.output


def test_update_check_fresh_null_version_entry_throttles(monkeypatch, tmp_path):
    """`"latest_version": null` is a valid throttle record, not a corrupt one.

    It is exactly what a failed refresh with nothing previously known writes, so
    reading it as "unusable, refresh now" would turn every such failure into an
    unthrottled probe on the very next invocation.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps({"checked_at": CHECKED_AT, "latest_version": None}),
        encoding="utf-8",
    )
    request = Mock(side_effect=AssertionError("a null-version record still throttles"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ""
    request.assert_not_called()


def test_update_check_skipped_when_session_is_not_interactive(monkeypatch, tmp_path):
    """The advisory never runs for a session that is not a terminal.

    ENG-6643's "never runs where it is inappropriate" criterion: a piped or
    redirected session (a script, a cron job, a `2>` capture) must get no network
    call and no cache file -- the advisory is for humans at a terminal only.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path, interactive=False)
    request = Mock(side_effect=AssertionError("non-interactive session must not check"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_not_called()
    # Not merely no *fresh* cache: the check returns before the cache path is
    # even computed, so nothing under XDG_CACHE_HOME is created or read.
    assert not _cache_path(tmp_path).exists()
    assert not _cache_path(tmp_path).parent.exists()


@pytest.mark.parametrize(
    ("stdout_tty", "stderr_tty", "expect_request"),
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
        ("raise", True, False),
    ],
    ids=[
        "both-tty",
        "stdout-piped",
        "stderr-redirected",
        "neither-tty",
        "isatty-raises",
    ],
)
def test_update_check_requires_both_streams_to_be_a_terminal(
    monkeypatch, tmp_path, stdout_tty, stderr_tty, expect_request
):
    """BOTH streams must be a terminal -- an stderr-only gate does not hold.

    `guard list assets | jq` redirects stdout and leaves stderr a tty, which is
    the piped, scripted, high-volume case whose cadence the gate exists to stop
    leaking. This test deliberately does NOT use the shared gate force: it drives
    the real `_session_is_interactive` through a substituted `sys`, so the
    `both-tty` row is a genuine positive (a request IS made) and the other rows
    are genuine negatives.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    monkeypatch.setattr(decorators, "sys", _SysShim(stdout_tty, stderr_tty))
    request = Mock(return_value=_response("1.9.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    if expect_request:
        request.assert_called_once_with(UPDATE_URL, timeout=2)
        assert "A new version of praetorian-cli is available: 1.9.0" in result.output
    else:
        request.assert_not_called()
        assert result.output == ""
        assert not _cache_path(tmp_path).parent.exists()


@pytest.mark.parametrize(
    ("name", "value"),
    [("CI", "1"), ("CI", "true"), ("GITHUB_ACTIONS", "1"), ("TERM", "dumb")],
    ids=["ci-one", "ci-true", "github-actions", "term-dumb"],
)
def test_update_check_skipped_by_non_interactive_environment(
    monkeypatch, tmp_path, name, value
):
    """A runner that allocates a pty is still not a human at a terminal.

    Both streams are forced to report a tty here, so the tty gate is open and each
    environment variable is the *only* thing that can close it -- which is what
    makes each row independent rather than incidentally passing on the tty check.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    monkeypatch.setattr(decorators, "sys", _SysShim(True, True))
    monkeypatch.setenv(name, value)
    request = Mock(side_effect=AssertionError("CI session must not check for updates"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_not_called()
    assert result.output == ""
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


def test_update_check_skipped_when_group_delegates_to_a_failing_subcommand(
    monkeypatch, tmp_path
):
    """A group callback delegating to a subcommand advises NOT AT ALL.

    Click runs a group callback BEFORE its subcommand, so without this gate
    `guard aegis list` printed the advisory ahead of the work the user asked for
    -- and still printed it when that work then failed, which is the one moment a
    user least wants an unrelated nag. Measured on the ungated code: the advisory
    appeared before the leaf ran and the request went out even though the command
    exited non-zero.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(return_value=_response("1.2.0"))
    monkeypatch.setattr(decorators.requests, "get", request)
    events = []

    result = CliRunner().invoke(_group_with_leaf(events, leaf_fails=True), ["leaf"], obj=object())

    assert result.exit_code == 1
    assert "leaf failed" in result.output
    assert events == ["group", "leaf"]
    request.assert_not_called()
    for fragment in ADVISORY_FRAGMENTS:
        assert fragment not in result.output


def test_update_check_advises_exactly_once_for_a_succeeding_subcommand(
    monkeypatch, tmp_path
):
    """Two `upgrade_check` wrappers on one invocation must still advise once.

    `guard aegis list` runs the group callback's check and the leaf's check. The
    group's is the one that is skipped, so the user gets exactly one advisory --
    measured on the ungated code, the same invocation printed all three lines
    twice.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(return_value=_response("1.2.0"))
    monkeypatch.setattr(decorators.requests, "get", request)
    events = []

    result = CliRunner().invoke(_group_with_leaf(events), ["leaf"], obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert events == ["group", "leaf"]
    for fragment in ADVISORY_FRAGMENTS:
        assert result.output.count(fragment) == 1
    request.assert_called_once_with(UPDATE_URL, timeout=2)


def test_update_check_advises_once_for_a_bare_group_invocation(monkeypatch, tmp_path):
    """Skipping delegation does not silence the group's own default path.

    `invoke_without_command=True` groups do real work when called bare (the TUI
    entry points), so that invocation is a leaf as far as the advisory is
    concerned. A gate keyed on "is a group" rather than "is delegating" would lose
    it.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    request = Mock(return_value=_response("1.2.0"))
    monkeypatch.setattr(decorators.requests, "get", request)
    events = []

    result = CliRunner().invoke(_group_with_leaf(events), [], obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert events == ["group", "group-default"]
    for fragment in ADVISORY_FRAGMENTS:
        assert result.output.count(fragment) == 1
    request.assert_called_once_with(UPDATE_URL, timeout=2)


@pytest.mark.parametrize(
    "exception",
    [KeyboardInterrupt(), SystemExit(73), CancelledError("cancelled")],
    ids=["keyboard-interrupt", "system-exit", "cancelled"],
)
def test_update_check_propagates_process_control_exceptions(
    monkeypatch, tmp_path, exception
):
    """The fail-open arms swallow failures, not process control.

    `except Exception` already lets `KeyboardInterrupt` and `SystemExit` through
    (both are `BaseException`), which is why it is written that way rather than as
    a bare `except:`. `concurrent.futures.CancelledError` is `Exception`-derived on
    this runtime, so the dedicated `except CancelledError: raise` arm is the only
    thing that keeps a cancelled command from being reported as a success.

    Called directly rather than through `CliRunner`, because the claim is about
    what leaves `_check_for_update` -- Click's standalone mode would translate
    each of these into an exit status and hide which one escaped.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setattr(decorators.requests, "get", Mock(side_effect=exception))

    with pytest.raises(type(exception)) as raised:
        decorators._check_for_update()

    assert raised.value is exception


def test_update_check_propagates_cancellation_from_the_cache_write(monkeypatch, tmp_path):
    """Cancellation during the *write* propagates too, not just during the fetch.

    The write has its own fail-open arm (it returns False rather than raising, so
    the caller can treat a failed write as "stay off the network"), which is
    exactly the shape that would turn a cancelled command into a silent success.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cancelled = CancelledError("cancelled")
    monkeypatch.setattr(
        decorators.requests, "get", Mock(side_effect=AssertionError("must not be reached"))
    )

    def cancelling_dump(*_args, **_kwargs):
        raise cancelled

    monkeypatch.setattr(decorators.json, "dump", cancelling_dump)

    with pytest.raises(CancelledError) as raised:
        decorators._check_for_update()

    assert raised.value is cancelled


@pytest.mark.parametrize(
    "exception",
    [PackageNotFoundError("praetorian-cli"), RuntimeError("boom"), OSError("offline")],
    ids=["package-not-found", "runtime-error", "os-error"],
)
def test_update_check_failure_after_the_fetch_is_still_fail_open(
    monkeypatch, tmp_path, exception
):
    """A failure raised OUTSIDE the fetch is swallowed too -- by the outer arm.

    This is the complement of the propagation test above, and it needs a failure
    that is not network-shaped: the fetch has its own guard, so every request-side
    failure is caught before the outer arm is reachable, which would leave that
    arm -- the one that decides whether the advisory can break a command at all --
    with nothing pinning it.

    Reading the local version is the realistic somewhere-else.
    `importlib.metadata.version` raises `PackageNotFoundError` whenever the CLI
    runs from a source tree with no installed distribution, which is the normal
    state of a developer checkout; that must not turn a command the user already
    completed into a failure.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setattr(decorators.requests, "get", Mock(return_value=_response("1.2.0")))

    def failing_version(_package):
        raise exception

    monkeypatch.setattr(decorators, "version", failing_version)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ""


def test_update_check_unparseable_local_version_is_silent(monkeypatch, tmp_path):
    """An unparseable *local* version is swallowed as well, not raised.

    Editable installs and vendored builds produce version strings `packaging`
    rejects, and the comparison against them is outside the fetch guard -- so
    `InvalidVersion` would escape as a command failure without the outer arm.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    monkeypatch.setattr(decorators, "version", lambda _package: "not-a-version")
    monkeypatch.setattr(decorators.requests, "get", Mock(return_value=_response("1.2.0")))

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ""


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
