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
import threading
from collections import namedtuple
from concurrent.futures import CancelledError
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.cli_decorators import (
    UPDATE_CHECK_CACHE_MAX_BYTES,
    UPDATE_CHECK_CACHE_TTL_SECONDS,
    UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS,
)


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

# Creating a *directory* symlink needs a privilege or developer mode off POSIX, so
# the symlink cases are skipped there rather than deleted -- the rejection they
# pin is what keeps a hostile pre-created cache directory from being written to.
symlinks_only = pytest.mark.skipif(
    os.name != "posix", reason="creating a directory symlink is not unprivileged off POSIX"
)

# `/dev/fd` is how this process's open descriptors are counted. Linux and macOS
# both have it; elsewhere there is nothing to count, so the leak test is skipped.
fd_counting_only = pytest.mark.skipif(
    not os.path.isdir("/dev/fd"), reason="descriptor counting needs /dev/fd"
)

# The cache write has two arms, chosen by `_cache_dir_descriptor_supported()`: a
# directory-descriptor arm, and a path fallback for the platforms without the
# descriptor primitives. The fallback is always reachable -- deleting `os.fchmod`
# simulates it -- but the descriptor arm cannot be simulated where the primitives
# do not exist, so cases specific to it are skipped there.
descriptor_writes_only = pytest.mark.skipif(
    not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "fchmod")),
    reason="the directory-descriptor arm needs os.O_NOFOLLOW and os.fchmod",
)

# A planted FIFO at the cache path is the availability vector that has no
# exception to catch: it parks `open()` in the kernel until a writer arrives.
fifos_only = pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="planting a FIFO needs os.mkfifo"
)

# `os.mknod` is not available unprivileged, so the device vector is reached with a
# symlink to a device that already exists. `/dev/zero` is the worst case on
# purpose: an unbounded read of it returns bytes forever.
DEVICE_PATH = "/dev/zero"


def _is_character_device(path: str) -> bool:
    try:
        return stat.S_ISCHR(os.stat(path).st_mode)
    except OSError:
        return False


character_devices_only = pytest.mark.skipif(
    not _is_character_device(DEVICE_PATH),
    reason=f"{DEVICE_PATH} is not a character device on this platform",
)


def _cache_path(cache_root: Path) -> Path:
    return cache_root / "praetorian-cli" / "update-check.json"


def _refresh_marker_path(cache_root: Path) -> Path:
    """The exclusive-create marker that serialises concurrent refreshes.

    Derived here the same way the module derives it -- a sibling of the cache
    record -- so a test can pre-create it (another invocation holds the claim) or
    assert its absence (the claim was released).
    """
    cache_path = _cache_path(cache_root)
    return cache_path.with_name(cache_path.name + ".refresh")


def _write_cache_record(cache_path: Path, checked_at, latest_version) -> None:
    """Leave the cache record a previous invocation -- or a peer -- would have left."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"checked_at": checked_at, "latest_version": latest_version}),
        encoding="utf-8",
    )


def _victim_directory(tmp_path: Path) -> Path:
    """A directory this user owns, world-readable and non-empty.

    Owned and writable ON PURPOSE: nothing but the module's own refusal stands
    between a refresh and writing in here, so a missing refusal shows up as a
    changed mode or a changed file rather than as an `OSError` the fail-open arm
    would have swallowed. The mode is set explicitly, not left to umask, because
    it is asserted afterwards.
    """
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keepme").write_bytes(b"not ours")
    (victim / "keepme").chmod(0o644)
    victim.chmod(0o755)
    return victim


def _symlinked_leaf_cache(tmp_path: Path):
    """A cache root whose `praetorian-cli` leaf is a pre-created symlink.

    Returns `(cache_root, victim)`. The target is a directory this user owns and
    can write, so nothing but the leaf-symlink rejection stands between the
    refresh and writing into it -- and it is world-readable and non-empty, so both
    its mode and its contents are observable afterwards.
    """
    victim = _victim_directory(tmp_path)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _cache_path(cache_root).parent.symlink_to(victim, target_is_directory=True)
    return cache_root, victim


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


_Replacement = namedtuple(
    "_Replacement",
    "mechanism raw_source raw_destination source_name destination_name "
    "source_directory destination_directory",
)


def _directory_identity(entry) -> tuple:
    """`(device, inode)` for a path or an open descriptor, or None for neither."""
    if entry is None:
        return None
    info = os.stat(entry)
    return (info.st_dev, info.st_ino)


def _record_atomic_cache_replacements(monkeypatch):
    """Record every atomic replacement a cache write performs, on either arm.

    The two arms replace the record by different primitives -- `os.rename`
    against a directory descriptor, and `os.replace` against full paths -- so
    both are patched and each call is normalised to one shape. `source_directory`
    and `destination_directory` are `(device, inode)` identities rather than path
    strings, because "the same directory, so the rename is atomic" is a statement
    about the directory the entry name is resolved against, which on the
    descriptor arm is a descriptor and has no path at all.

    The primitive actually used is recorded too, so a test can pin which arm ran
    rather than merely that *something* replaced the file.
    """
    replacements = []
    real_rename = os.rename
    real_replace = os.replace

    def record_rename(source, destination, *, src_dir_fd=None, dst_dir_fd=None):
        replacements.append(
            _Replacement(
                "os.rename",
                str(source),
                str(destination),
                Path(source).name,
                Path(destination).name,
                _directory_identity(src_dir_fd),
                _directory_identity(dst_dir_fd),
            )
        )
        real_rename(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

    def record_replace(source, destination):
        replacements.append(
            _Replacement(
                "os.replace",
                str(source),
                str(destination),
                Path(source).name,
                Path(destination).name,
                _directory_identity(Path(source).parent),
                _directory_identity(Path(destination).parent),
            )
        )
        real_replace(source, destination)

    monkeypatch.setattr(os, "rename", record_rename)
    monkeypatch.setattr(os, "replace", record_replace)
    return replacements


@pytest.mark.parametrize(
    "descriptor_support",
    [
        pytest.param(True, marks=descriptor_writes_only, id="directory-descriptor"),
        pytest.param(False, id="path-fallback"),
    ],
)
def test_update_check_cached_payload_is_atomically_replaced_twice(
    monkeypatch, tmp_path, descriptor_support
):
    """A refresh replaces the cache file TWICE, and every replace is atomic.

    Two by design, not by accident: the first records the attempt *before* the
    request goes out (which is what throttles a failing refresh), the second
    records its result. Each one writes a temporary entry beside the destination
    and then renames it over the destination in a single same-directory
    operation, so a reader never sees a partially written file and neither leaves
    the temp entry behind.

    Both write arms are exercised, because the property is the atomicity and not
    the call. Where the directory-descriptor primitives exist, the temporary is
    created and renamed *relative to an open descriptor on the cache directory*
    (`os.rename` with `src_dir_fd`/`dst_dir_fd`, which takes bare entry names and
    never resolves the path a second time -- that second resolution is the TOCTOU
    window). Where they do not -- Windows -- the fallback keeps `tempfile.mkstemp`
    plus `os.replace` on full paths. Windows is simulated rather than skipped, for
    the reason spelled out in
    `test_update_check_survives_a_platform_without_os_fchmod`.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    if not descriptor_support:
        monkeypatch.delattr(os, "fchmod", raising=False)
    assert decorators._cache_dir_descriptor_supported() == descriptor_support
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir()
    cache_path.write_text("malformed", encoding="utf-8")
    cache_directory = _directory_identity(cache_path.parent)
    request = Mock(return_value=_response("1.4.0"))
    monkeypatch.setattr(decorators.requests, "get", request)
    replacements = _record_atomic_cache_replacements(monkeypatch)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert len(replacements) == 2
    for replacement in replacements:
        assert replacement.mechanism == ("os.rename" if descriptor_support else "os.replace")
        assert replacement.destination_name == cache_path.name
        assert replacement.source_name != replacement.destination_name
        assert replacement.source_directory == cache_directory
        assert replacement.destination_directory == cache_directory
        assert not (cache_path.parent / replacement.source_name).exists()
        if descriptor_support:
            # A descriptor-relative rename takes BARE entry names; a full path
            # here would be resolved against the process cwd, not the descriptor.
            assert replacement.raw_source == replacement.source_name
            assert replacement.raw_destination == cache_path.name
        else:
            assert Path(replacement.raw_destination) == cache_path
            assert Path(replacement.raw_source).parent == cache_path.parent
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


# --------------------------------------------------------------------------- #
# Concurrent refresh exclusion.
#
# One exclusive-create marker beside the cache record elects one refresher out of
# N simultaneous invocations. Real concurrency cannot be scheduled deterministically
# in one process, so these tests drive the two halves of the race separately: the
# LOSER's half by pre-creating the marker, and the WINNER-that-arrived-late half by
# letting a peer land its record between the claim and the re-read.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "marker_age",
    [0, UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS],
    ids=["just-claimed", "at-the-staleness-boundary"],
)
def test_update_check_lost_refresh_claim_makes_no_request(
    monkeypatch, tmp_path, marker_age
):
    """Whoever loses the claim does not fetch: N invocations, one probe.

    Both ages are held by another invocation. The boundary case is the one an
    off-by-one reclaim would get wrong: a marker exactly at the staleness constant
    is *not* yet stale, so treating the comparison as `<` instead of `<=` would let
    a second invocation reclaim it and probe concurrently with the holder.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    # Stale, so the refresh branch is the one taken and the claim is attempted.
    _write_cache_record(cache_path, 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"")
    os.utime(marker, (CHECKED_AT - marker_age, CHECKED_AT - marker_age))
    request = Mock(side_effect=AssertionError("a lost refresh claim must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_not_called()


def test_update_check_lost_refresh_claim_still_advises(monkeypatch, tmp_path):
    """Losing the claim skips the REFRESH, not the whole check.

    The cached version is still compared against the local one and still printed.
    An implementation that returned early on a lost claim would silence the
    advisory for every invocation that happens to collide with a refresh -- and
    under a shell that runs several `guard` commands at once, that is most of them.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    _write_cache_record(_cache_path(tmp_path), 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"")
    os.utime(marker, (CHECKED_AT, CHECKED_AT))
    request = Mock(side_effect=AssertionError("a lost refresh claim must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert "A new version of praetorian-cli is available: 1.2.0" in result.output
    assert result.exit_code == 0
    request.assert_not_called()


def test_update_check_lost_refresh_claim_leaves_the_holders_marker(monkeypatch, tmp_path):
    """The loser does not release a marker it never claimed.

    This is the whole exclusion: a loser that unlinked the holder's marker in its
    own `finally` would hand the claim straight back to the next arrival, and N
    invocations would probe N times again -- with the added hazard that the holder
    is still mid-fetch and will release a marker that by then belongs to someone
    else.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    _write_cache_record(_cache_path(tmp_path), 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"held")
    os.utime(marker, (CHECKED_AT, CHECKED_AT))
    request = Mock(side_effect=AssertionError("a lost refresh claim must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert marker.exists()
    assert marker.read_bytes() == b"held"
    assert result.exit_code == 0
    request.assert_not_called()


def test_update_check_stale_refresh_marker_is_reclaimed(monkeypatch, tmp_path):
    """A marker left behind by a killed invocation cannot wedge refreshes forever.

    One second past the staleness constant is enough: the marker is only an
    election, so the recovery window is deliberately short compared to the cache
    TTL. Without the reclaim, a single `SIGKILL` during a fetch would suppress
    every future refresh for the lifetime of the cache directory.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    _write_cache_record(_cache_path(tmp_path), 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"")
    abandoned_at = CHECKED_AT - (UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS + 1)
    os.utime(marker, (abandoned_at, abandoned_at))
    assert UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS < UPDATE_CHECK_CACHE_TTL_SECONDS
    request = Mock(return_value=_response("1.8.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert result.exit_code == 0
    assert "A new version of praetorian-cli is available: 1.8.0" in result.output


def test_update_check_future_dated_refresh_marker_is_reclaimed(monkeypatch, tmp_path):
    """A marker stamped in the FUTURE ages out too, instead of wedging refreshes.

    A negative age is what a filesystem clock running ahead of ours, a restored
    backup, or a copied home directory leaves behind, and it is unbounded in a way
    a positive age is not: a marker a day in the future suppresses every refresh
    for that whole day plus the staleness window if the bound only looks at the
    positive side. The assertion is on the fetch count rather than on the claim's
    return value, because the fetch is the behaviour the user loses.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    _write_cache_record(_cache_path(tmp_path), 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"stamped ahead")
    a_day_ahead = CHECKED_AT + 24 * 60 * 60
    os.utime(marker, (a_day_ahead, a_day_ahead))
    request = Mock(return_value=_response("1.9.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert result.exit_code == 0
    assert "A new version of praetorian-cli is available: 1.9.0" in result.output
    # Reclaimed, used, and released -- not merely reclaimed.
    assert not marker.exists()


@pytest.mark.parametrize(
    "skew_seconds",
    [5, 30, UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS],
    ids=["five-seconds-ahead", "thirty-seconds-ahead", "at-the-negative-boundary"],
)
def test_update_check_refresh_marker_stamped_by_a_fast_clock_still_holds(
    monkeypatch, tmp_path, skew_seconds
):
    """A LIVE holder's marker is not reclaimed merely for reading as future-dated.

    The tolerance is symmetric by policy, not by accident. A network filesystem
    whose clock runs a few seconds ahead of this host stamps every marker in our
    future, and a bound that tolerated only the positive side (`0 <= age <= S`)
    would reclaim all of them the moment they were created -- the exclusion
    failing open, N invocations probing together, which is the one thing the
    marker exists to prevent. Modest skew is therefore *held*, and the negative
    edge is inclusive, so a skew of exactly the staleness constant still holds.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    # Stale, so the refresh branch is the one taken and the claim is attempted.
    _write_cache_record(_cache_path(tmp_path), 0, "1.2.0")
    marker = _refresh_marker_path(tmp_path)
    marker.write_bytes(b"held")
    stamped_ahead = CHECKED_AT + skew_seconds
    os.utime(marker, (stamped_ahead, stamped_ahead))
    request = Mock(side_effect=AssertionError("a live holder's marker must not be reclaimed"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    request.assert_not_called()
    # The holder's marker is left exactly as it was, mtime included.
    assert marker.read_bytes() == b"held"
    assert marker.stat().st_mtime == stamped_ahead


def test_update_check_refresh_marker_is_released_when_the_fetch_raises(
    monkeypatch, tmp_path
):
    """The claim is released on the failure paths too, not only on success.

    The release lives in a `finally`, which is what this asserts: a marker left
    behind by a raising fetch would suppress refreshes until it aged out of the
    staleness window, turning one unreachable index into a stall on every
    invocation in that window.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    _write_cache_record(_cache_path(tmp_path), 0, None)
    marker = _refresh_marker_path(tmp_path)
    request = Mock(side_effect=OSError("name or service not known"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert not marker.exists()
    assert result.exit_code == 0
    assert result.exception is None
    assert request.call_count == 1


def test_update_check_released_marker_lets_the_next_stale_invocation_refresh(
    monkeypatch, tmp_path
):
    """The consequence of the release: the next stale invocation can still refresh.

    The TTL throttle is deliberately stepped over between the two invocations, so
    the only thing that could stop the second refresh is a marker the first one
    failed to release -- and under the frozen clock any leftover marker is inside
    the staleness window, so the claim would be lost and the request count would
    stay at one.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    _write_cache_record(cache_path, 0, None)
    request = Mock(side_effect=OSError("name or service not known"))
    monkeypatch.setattr(decorators.requests, "get", request)

    first = CliRunner().invoke(_successful_command(), obj=object())
    assert first.exit_code == 0
    assert request.call_count == 1

    # Age the throttle record back out of the TTL window, so the second
    # invocation reaches the claim at all.
    _write_cache_record(cache_path, 0, None)
    request.side_effect = None
    request.return_value = _response("1.9.0")

    second = CliRunner().invoke(_successful_command(), obj=object())

    assert request.call_count == 2
    assert second.exit_code == 0
    assert "A new version of praetorian-cli is available: 1.9.0" in second.output


def _claim_then_let_a_peer_refresh(decorators, monkeypatch, cache_path, peer_at, peer_version):
    """Win the claim, then let a peer land `peer_version` before the re-read.

    This is the late-arrival half of the race: two invocations read the same stale
    record, one wins the claim and fetches, and the other wins it *afterwards* --
    by which point the answer it needs is already on disk. Patching the claim is
    the only deterministic seam for it, because the peer's write has to land
    strictly between this invocation's claim and its re-read.
    """
    real_claim = decorators._claim_update_refresh_marker

    def claim_then_peer_refreshes(path):
        claimed = real_claim(path)
        _write_cache_record(cache_path, peer_at, peer_version)
        return claimed

    monkeypatch.setattr(
        decorators, "_claim_update_refresh_marker", claim_then_peer_refreshes
    )


def test_update_check_claim_winner_stands_down_for_a_peers_fresh_record(
    monkeypatch, tmp_path
):
    """A claim won *after* a peer refreshed makes ZERO requests.

    Without the re-read inside the claim, the exclusion only narrows the race
    window instead of closing it: every invocation that queues up behind the
    holder claims the marker in turn the moment it is released, and each one
    fetches on the strength of the stale record it read before it ever waited.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    _write_cache_record(cache_path, 0, "1.2.0")
    request = Mock(side_effect=AssertionError("a peer's fresh record must not be re-fetched"))
    monkeypatch.setattr(decorators.requests, "get", request)
    _claim_then_let_a_peer_refresh(decorators, monkeypatch, cache_path, CHECKED_AT, "1.5.0")

    result = CliRunner().invoke(_successful_command(), obj=object())

    request.assert_not_called()
    assert result.exit_code == 0
    assert result.exception is None
    assert not _refresh_marker_path(tmp_path).exists()


def test_update_check_claim_winner_advises_the_peers_version(monkeypatch, tmp_path):
    """Standing down still advises -- with the PEER's version, not the stale one.

    The invocation read 1.2.0 at entry and the peer replaced it with 1.5.0 while
    the claim was being taken. Serving the entry-time value would advertise a
    version the process already knows to be superseded, and would keep doing so
    for as long as invocations kept colliding.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    _write_cache_record(cache_path, 0, "1.2.0")
    request = Mock(side_effect=AssertionError("a peer's fresh record must not be re-fetched"))
    monkeypatch.setattr(decorators.requests, "get", request)
    _claim_then_let_a_peer_refresh(decorators, monkeypatch, cache_path, CHECKED_AT, "1.5.0")

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert "A new version of praetorian-cli is available: 1.5.0" in result.output
    assert "1.2.0" not in result.output
    assert result.exit_code == 0
    request.assert_not_called()


def test_update_check_peer_record_freshness_is_judged_by_the_clock_read_after_the_claim(
    monkeypatch, tmp_path
):
    """The re-read samples the clock AGAIN; it must not reuse the pre-claim `now`.

    Time passes while an invocation waits for the claim, so the peer's record can
    carry a timestamp *later* than the `now` this invocation captured on entry.
    Judged against that stale `now`, the age is negative, the future-timestamp rule
    scores the peer's record as stale, and the invocation refetches -- which is the
    exact stampede the re-read exists to prevent, restored in the one case where
    contention is highest. Judged against a fresh reading, the age is positive and
    the invocation stands down.

    The clock is keyed on whether the peer has written rather than on call order,
    so the discrimination does not depend on how many times `time.time()` happens
    to be consulted.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    _write_cache_record(cache_path, 0, "1.2.0")
    request = Mock(side_effect=AssertionError("a peer's fresh record must not be re-fetched"))
    monkeypatch.setattr(decorators.requests, "get", request)

    peer_written = []
    monkeypatch.setattr(
        decorators.time, "time", lambda: CHECKED_AT + 10 if peer_written else CHECKED_AT
    )

    real_claim = decorators._claim_update_refresh_marker

    def claim_then_peer_refreshes(path):
        claimed = real_claim(path)
        # Written 5s after this invocation's entry -- ahead of the pre-claim `now`,
        # behind the clock as it reads once the claim has been taken.
        _write_cache_record(cache_path, CHECKED_AT + 5, "1.5.0")
        peer_written.append(True)
        return claimed

    monkeypatch.setattr(
        decorators, "_claim_update_refresh_marker", claim_then_peer_refreshes
    )

    result = CliRunner().invoke(_successful_command(), obj=object())

    request.assert_not_called()
    assert "A new version of praetorian-cli is available: 1.5.0" in result.output
    assert result.exit_code == 0
    # The peer's record is left exactly as the peer wrote it: standing down writes
    # nothing, so the peer's timestamp is not walked backwards to this
    # invocation's older `now`.
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "checked_at": CHECKED_AT + 5,
        "latest_version": "1.5.0",
    }


# --------------------------------------------------------------------------- #
# `XDG_CACHE_HOME` that is not an absolute path.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cache_home",
    ["relative-cache", "./relative-cache", ""],
    ids=["relative", "dot-relative", "empty"],
)
def test_update_check_non_absolute_xdg_cache_home_falls_back_to_the_home_cache(
    monkeypatch, tmp_path, cache_home
):
    """A non-absolute `XDG_CACHE_HOME` is ignored, per the XDG base-directory spec.

    Honouring it would resolve the cache against the *current working directory*,
    so `guard` would scatter a cache directory into whatever tree the user happened
    to be standing in -- and, worse, would read a throttle record written by
    whoever else can write there. The empty value is the case that was already
    correct and is easy to break, since it is falsey rather than non-absolute.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    working_dir = tmp_path / "cwd"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("XDG_CACHE_HOME", cache_home)
    request = Mock(return_value=_response("2.0.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    resolved = decorators._update_check_cache_path()

    assert resolved.is_absolute()
    assert resolved == fake_home / ".cache" / "praetorian-cli" / "update-check.json"

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert "A new version of praetorian-cli is available: 2.0.0" in result.output
    assert json.loads(resolved.read_text(encoding="utf-8"))["latest_version"] == "2.0.0"
    # Nothing was resolved against the working directory.
    assert list(working_dir.iterdir()) == []


# --------------------------------------------------------------------------- #
# A cache directory that is a symlink.
# --------------------------------------------------------------------------- #


@symlinks_only
def test_update_check_symlinked_cache_directory_stays_off_the_network(
    monkeypatch, tmp_path
):
    """A cache directory that is a symlink is refused, so ZERO requests are made.

    This is the consequence that actually matters: the write is the throttle, so a
    cache directory that cannot be written is an environment whose probe rate
    cannot be limited -- and it must not be probed at all, not once per invocation.
    Three invocations, because a rejection that failed to stop the fetch would show
    up as a request every time rather than only on the first.
    """
    cache_root, _victim = _symlinked_leaf_cache(tmp_path)
    decorators = _configure_update_check(monkeypatch, cache_root)
    request = Mock(side_effect=AssertionError("a symlinked cache directory must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    for _ in range(3):
        result = CliRunner().invoke(_successful_command(), obj=object())
        assert result.exit_code == 0
        assert result.exception is None
        assert ADVISORY_LEAD not in result.output

    request.assert_not_called()


@symlinks_only
def test_update_check_symlinked_cache_directory_writes_nothing_into_the_target(
    monkeypatch, tmp_path
):
    """Nothing is created inside the symlink target -- not the record, not a temp file.

    A pre-created symlink is how an attacker who can write the cache path but not
    the target aims a privileged write somewhere else; `mkstemp` plus `os.replace`
    would follow the link and land both files in the target directory.
    """
    cache_root, victim = _symlinked_leaf_cache(tmp_path)
    decorators = _configure_update_check(monkeypatch, cache_root)
    request = Mock(side_effect=AssertionError("a symlinked cache directory must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert sorted(p.name for p in victim.iterdir()) == ["keepme"]
    assert (victim / "keepme").read_bytes() == b"not ours"
    assert result.exit_code == 0
    request.assert_not_called()


@symlinks_only
@posix_modes_only
def test_update_check_symlinked_cache_directory_keeps_the_targets_mode(
    monkeypatch, tmp_path
):
    """The target's mode is unchanged: the 0700 repair does not follow the link.

    The directory preparation deliberately *repairs* a too-permissive mode, which
    is exactly why the symlink case has to be refused before it runs -- otherwise
    the repair reaches through the link and re-modes a directory that is none of
    its business.
    """
    cache_root, victim = _symlinked_leaf_cache(tmp_path)
    decorators = _configure_update_check(monkeypatch, cache_root)
    request = Mock(return_value=_response("2.2.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert stat.S_IMODE(victim.stat().st_mode) == 0o755
    assert result.exit_code == 0


@symlinks_only
def test_update_check_write_to_a_symlinked_cache_directory_reports_failure(
    monkeypatch, tmp_path
):
    """`_write_update_check_cache` reports the refusal, rather than claiming success.

    The return value is what the caller reads to decide whether to fetch, so a
    refusal reported as success would restore the unthrottled probe -- the network
    assertion above is downstream of this one.
    """
    cache_root, _victim = _symlinked_leaf_cache(tmp_path)
    decorators = _configure_update_check(monkeypatch, cache_root)

    assert not decorators._write_update_check_cache(
        _cache_path(cache_root), CHECKED_AT, "1.2.0"
    )


@symlinks_only
def test_update_check_symlinked_cache_ancestor_still_works(monkeypatch, tmp_path):
    """The rejection is scoped to the leaf: a symlinked ANCESTOR still works.

    A symlinked `~/.cache` is a normal dotfile-manager or shared-cache-volume
    setup, and rejecting it would silently disable the advisory for those users.
    The leaf is the component the module creates itself, so it is the only one it
    can hold to having not been pre-created by somebody else.
    """
    real_cache = tmp_path / "real-cache"
    real_cache.mkdir()
    linked_cache = tmp_path / "linked-cache"
    linked_cache.symlink_to(real_cache, target_is_directory=True)
    decorators = _configure_update_check(monkeypatch, linked_cache)
    request = Mock(return_value=_response("2.1.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    result = CliRunner().invoke(_successful_command(), obj=object())

    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert result.exit_code == 0
    assert "A new version of praetorian-cli is available: 2.1.0" in result.output
    assert json.loads(
        _cache_path(real_cache).read_text(encoding="utf-8")
    )["latest_version"] == "2.1.0"


# --------------------------------------------------------------------------- #
# The leaf directory swapped for a symlink MID-FLIGHT.
#
# The section above plants the symlink before the run starts, which a check
# ordered before the first write already catches. These two plant it in the
# window the module opens itself: between creating the leaf and using it. Anything
# that names the leaf BY PATH after that point resolves the attacker's link, so
# what is asserted here is the VICTIM -- its mode and its bytes -- and not merely
# the returned False, which one of the two windows already returned before the fix.
# --------------------------------------------------------------------------- #


def _swap_the_leaf_for_a_symlink_after_mkdir(monkeypatch, leaf: Path, victim: Path):
    """Hand the race to the attacker: swap `leaf` for a symlink as its `mkdir` returns.

    `Path.mkdir` is the moment the leaf comes into existence and the last moment
    before anything looks at it, so it is the window a racing attacker actually
    gets. Returns the (single-element) record of the swap, so a test can prove the
    race was RUN -- a swap that never fired would leave every assertion below
    passing over an ordinary directory.

    Fires once, deliberately: the module tolerates `FileExistsError` and retries
    against whatever now sits at the path, and that second look must refuse it too.
    """
    real_mkdir = Path.mkdir
    swapped = []

    def mkdir(self, *args, **kwargs):
        real_mkdir(self, *args, **kwargs)
        if not swapped and self == leaf:
            self.rmdir()
            self.symlink_to(victim, target_is_directory=True)
            swapped.append(str(self))

    monkeypatch.setattr(Path, "mkdir", mkdir)
    return swapped


@symlinks_only
@posix_modes_only
@descriptor_writes_only
def test_update_check_leaf_swapped_after_mkdir_leaves_the_targets_mode(
    monkeypatch, tmp_path
):
    """Losing the race at `mkdir` refuses -- and does NOT re-mode the target.

    The 0700 repair is the payload here. Validating the leaf by PATH and then
    re-moding it by PATH resolves it twice, and the swap lands between the two: the
    repair reaches through the link and locks a directory that is none of our
    business down to 0700 (measured on the pre-fix code: 0o755 -> 0o700). Holding a
    DESCRIPTOR across both steps is what closes it -- `os.fstat` and `os.fchmod`
    address the inode that was vetted, and cannot be redirected by a later swap.

    The mode is the assertion, not the return value: the return was already False
    in this window before the fix, while the victim had already been re-moded.

    Scoped to the descriptor arm because that is the only arm that CAN close this
    window -- measured, forcing `_cache_dir_descriptor_supported()` false fails
    both of these -- and every platform with POSIX mode bits has the primitives.
    """
    victim = _victim_directory(tmp_path)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    decorators = _configure_update_check(monkeypatch, cache_root)
    cache_path = _cache_path(cache_root)
    swapped = _swap_the_leaf_for_a_symlink_after_mkdir(monkeypatch, cache_path.parent, victim)

    prepared = decorators._prepare_update_check_cache_dir(cache_path)

    assert swapped, "the race never ran: the leaf mkdir was not reached"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o755
    assert sorted(p.name for p in victim.iterdir()) == ["keepme"]
    assert not prepared


@symlinks_only
@posix_modes_only
@descriptor_writes_only
def test_update_check_leaf_swapped_after_mkdir_leaves_the_targets_file(
    monkeypatch, tmp_path
):
    """The same swap through the WRITE: the target's own file survives it untouched.

    A cache record the attacker has aimed elsewhere is not only a write in the
    wrong directory -- it OVERWRITES whatever already answers to that name there,
    with our bytes and our 0600 (measured on the pre-fix code: `b"not ours"` at
    0o644 became our JSON at 0o600, destroying a file and closing it to its own
    group). The write therefore re-validates on its own terms rather than trusting
    its caller, and addresses the record by `dir_fd` so the directory it vetted is
    the directory it writes in.
    """
    victim = _victim_directory(tmp_path)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    decorators = _configure_update_check(monkeypatch, cache_root)
    cache_path = _cache_path(cache_root)
    # Same NAME the record would be written under, so an unvalidated write
    # clobbers it rather than landing beside it.
    planted = victim / cache_path.name
    planted.write_bytes(b"not ours")
    planted.chmod(0o644)
    swapped = _swap_the_leaf_for_a_symlink_after_mkdir(monkeypatch, cache_path.parent, victim)

    written = decorators._write_update_check_cache(cache_path, CHECKED_AT, "1.2.0")

    assert swapped, "the race never ran: the leaf mkdir was not reached"
    assert planted.read_bytes() == b"not ours"
    assert stat.S_IMODE(planted.stat().st_mode) == 0o644
    assert stat.S_IMODE(victim.stat().st_mode) == 0o755
    # No temporary left behind in the target either, which is where `mkstemp`
    # would have put it.
    assert sorted(p.name for p in victim.iterdir()) == sorted(["keepme", cache_path.name])
    assert not written


# --------------------------------------------------------------------------- #
# A hostile cache RECORD.
#
# The cache path is a predictable name under `$XDG_CACHE_HOME`, so anything that
# can create one entry there chooses what `_read_update_check_cache` opens. Three
# distinct consequences, and they are not interchangeable: two are availability
# (the read never returns) and one is integrity (the read returns an attacker's
# answer). Every case below therefore asserts on the *return*, bounded by a
# deadline -- not on which guard rejected it.
# --------------------------------------------------------------------------- #


def _read_cache_within(decorators, cache_path: Path, seconds: float = 5.0):
    """`_read_update_check_cache(cache_path)`, on a thread, under a deadline.

    The availability vectors here fail by BLOCKING rather than by raising: a
    planted FIFO parks `open()` in the kernel with nothing raised, so neither the
    read's own `except (KeyError, OSError, TypeError, ValueError)` nor the
    advisory's outer fail-open arm can turn it into a skipped check. An
    unhardened implementation must therefore fail this call rather than hang the
    suite, which is what the deadline is for -- and the thread is a daemon so a
    hung mutant cannot keep the interpreter alive at exit either.
    """
    outcome = []

    def call():
        try:
            outcome.append(("returned", decorators._read_update_check_cache(cache_path)))
        except BaseException as error:  # reported below, never swallowed
            outcome.append(("raised", error))

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), f"the cache read did not return within {seconds}s"
    kind, value = outcome[0]
    assert kind == "returned", f"the cache read raised {value!r}"
    return value


@fifos_only
def test_update_check_cache_record_that_is_a_fifo_is_refused_promptly(monkeypatch, tmp_path):
    """A FIFO at the cache path returns None instead of blocking the CLI forever.

    This is the one vector with no exception to catch: with a FIFO and no writer,
    a blocking `open()` never returns and never raises, so `guard <anything>`
    simply stops before running the user's command. The failure mode this pins is
    a HANG, not a raise -- which is why the read is bounded by a deadline here
    rather than merely asserted to be None.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True)
    os.mkfifo(cache_path)

    assert _read_cache_within(decorators, cache_path) is None


@symlinks_only
@character_devices_only
def test_update_check_cache_record_symlinked_to_a_device_is_refused(monkeypatch, tmp_path):
    """A cache path linked at a device returns None without reading the device.

    `/dev/zero` yields bytes for as long as anything asks, so a reader that treats
    whatever it opened as a small JSON file resolves the link and then allocates
    until the process dies. The deadline is the assertion that matters: it fails
    on an implementation that reads to completion, where a plain `is None` would
    wait for the OOM killer.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True)
    cache_path.symlink_to(DEVICE_PATH)

    assert _read_cache_within(decorators, cache_path) is None


@symlinks_only
def test_update_check_cache_record_symlinked_to_a_valid_record_is_refused(
    monkeypatch, tmp_path
):
    """A symlinked record is refused even when the target parses -- the INTEGRITY vector.

    Distinct from the availability cases above, and the reason the refusal cannot
    be softened for targets that look harmless. An attacker who can create the
    cache path but not write our directory plants a link to a record of their own,
    stamped now and naming the installed version as the latest: the advisory is
    then pinned off and the user is never told about a security release. The
    consequence is asserted twice -- the record is not read, and the check
    therefore is not fresh, so the refresh goes ahead and reaches the real index.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True)
    planted = tmp_path / "planted-record.json"
    _write_cache_record(planted, CHECKED_AT, LOCAL_VERSION)
    cache_path.symlink_to(planted)
    request = Mock(return_value=_response("1.9.0"))
    monkeypatch.setattr(decorators.requests, "get", request)

    assert _read_cache_within(decorators, cache_path) is None
    assert not decorators._update_check_cache_is_fresh(
        decorators._read_update_check_cache(cache_path), CHECKED_AT
    )

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    request.assert_called_once_with(UPDATE_URL, timeout=2)
    assert "A new version of praetorian-cli is available: 1.9.0" in result.output
    # The record was replaced, not written *through* the link.
    assert json.loads(planted.read_text(encoding="utf-8"))["latest_version"] == LOCAL_VERSION


@pytest.mark.parametrize(
    "padded_to, accepted",
    [
        pytest.param(None, True, id="an-ordinary-record"),
        pytest.param(UPDATE_CHECK_CACHE_MAX_BYTES, True, id="exactly-at-the-size-cap"),
        pytest.param(
            UPDATE_CHECK_CACHE_MAX_BYTES + 1, False, id="one-byte-over-the-size-cap"
        ),
    ],
)
def test_update_check_cache_record_is_read_only_up_to_the_size_cap(
    monkeypatch, tmp_path, padded_to, accepted
):
    """The cap is pinned from BOTH sides: at the cap parses, one byte over does not.

    A cap asserted only from above is satisfied by refusing everything, which
    would disable the cache and restore the unthrottled probe -- so the accepted
    cases are as load-bearing as the refused one. Trailing whitespace is valid
    JSON, so between the two boundary cases the only thing that differs is the
    byte count.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True)
    record = json.dumps({"checked_at": CHECKED_AT, "latest_version": "1.2.0"}).encode()
    if padded_to is not None:
        record += b" " * (padded_to - len(record))
        assert len(record) == padded_to
    cache_path.write_bytes(record)

    cached = _read_cache_within(decorators, cache_path)

    if accepted:
        assert cached == (CHECKED_AT, decorators._parse_version("1.2.0"))
    else:
        assert cached is None


@posix_modes_only
def test_update_check_cache_record_owned_by_another_user_is_refused(monkeypatch, tmp_path):
    """A record this user does not own is refused, rather than parsed.

    Only root can actually chown a file to somebody else, so the *other* half of
    the comparison is moved instead: the effective uid the read checks against is
    replaced, which is indistinguishable from the record's point of view and needs
    no privilege. A shared or pre-seeded `$XDG_CACHE_HOME` -- a container image
    layer, a multi-user build agent -- is where a foreign-owned record comes from,
    and it is the same integrity problem as the symlink above without the symlink.
    """
    decorators = _configure_inputs(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True)
    _write_cache_record(cache_path, CHECKED_AT, "1.2.0")
    owner = os.stat(cache_path).st_uid
    monkeypatch.setattr(decorators.os, "geteuid", lambda: owner + 1)

    assert _read_cache_within(decorators, cache_path) is None


# --------------------------------------------------------------------------- #
# Descriptor accounting on the cache-write failure path.
# --------------------------------------------------------------------------- #


@fd_counting_only
def test_update_check_leaks_no_descriptor_when_fdopen_raises(monkeypatch, tmp_path):
    """`mkstemp` hands back a raw descriptor, and a failed `os.fdopen` must not orphan it.

    Only `os.fdopen` succeeding transfers ownership of that descriptor to a file
    object the `with` block can close; if it raises, nothing else will ever close
    it. The count is taken across 200 induced failures because one leak is
    invisible -- and a long-lived process on a `guard` install that hits this path
    every invocation is exactly where it stops being invisible.

    The path-only assertion is the one that missed this bug: the old code removed
    the temp file and leaked its descriptor, so `iterdir()` looked spotless while
    the process bled descriptors. Both are asserted here for that reason.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)
    request = Mock(side_effect=AssertionError("a cache that cannot be written must not probe"))
    monkeypatch.setattr(decorators.requests, "get", request)

    def refuse_to_wrap(*_args, **_kwargs):
        raise OSError("too many open files")

    monkeypatch.setattr(decorators.os, "fdopen", refuse_to_wrap)

    # One failing invocation before the baseline, so any one-time allocation on
    # this path is counted as setup rather than as a leak.
    warm_up = CliRunner().invoke(_successful_command(), obj=object())
    assert warm_up.exit_code == 0
    baseline = len(os.listdir("/dev/fd"))

    for _ in range(200):
        result = CliRunner().invoke(_successful_command(), obj=object())
        assert result.exit_code == 0
        assert result.exception is None

    assert len(os.listdir("/dev/fd")) == baseline
    request.assert_not_called()
    # No `mkstemp` leftover, and no cache record: the write never completed.
    assert list(cache_path.parent.iterdir()) == []


@fd_counting_only
@descriptor_writes_only
@pytest.mark.parametrize(
    "operation",
    ["prepare", "write", "failed-write"],
    ids=["preparing-the-directory", "writing-the-record", "a-write-that-raises"],
)
def test_update_check_reclaims_the_cache_directory_descriptor(
    monkeypatch, tmp_path, operation
):
    """The DIRECTORY descriptor is reclaimed too -- on success and on failure.

    Validating the directory by descriptor rather than by path means there is now
    a second long-lived descriptor per invocation, opened before the record is
    written and useless afterwards. On a long-lived `guard` process this path runs
    once per invocation, so a directory descriptor held one iteration too long is
    a slow file-descriptor exhaustion that ends with the CLI unable to open
    anything -- the advisory taking the whole tool down, which is the failure mode
    this module exists to avoid.

    All three arms count, because they close at three different places: the
    preparation opens one only to answer a question and must drop it immediately,
    the write must drop it after a successful record, and a write that RAISES must
    drop it on the way out -- the arm a `try`/`finally` is there for.
    """
    decorators = _configure_update_check(monkeypatch, tmp_path)
    cache_path = _cache_path(tmp_path)

    if operation == "prepare":
        def once():
            assert decorators._prepare_update_check_cache_dir(cache_path)
    elif operation == "write":
        def once():
            assert decorators._write_update_check_cache(cache_path, CHECKED_AT, "1.2.0")
    else:
        def refuse_to_wrap(*_args, **_kwargs):
            raise OSError("too many open files")

        monkeypatch.setattr(decorators.os, "fdopen", refuse_to_wrap)

        def once():
            assert not decorators._write_update_check_cache(cache_path, CHECKED_AT, "1.2.0")

    # One call before the baseline, so a one-time allocation on this path is
    # counted as setup rather than as a leak.
    once()
    baseline = len(os.listdir("/dev/fd"))

    for _ in range(200):
        once()

    assert len(os.listdir("/dev/fd")) == baseline
