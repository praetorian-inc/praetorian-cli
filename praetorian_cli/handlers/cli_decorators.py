import json
import os
import sys
import tempfile
import time
from concurrent.futures import CancelledError
from functools import wraps
from importlib.metadata import version
from pathlib import Path

import click
import requests
from packaging.version import InvalidVersion, Version

from praetorian_cli.handlers.utils import error


DEBUG_HINT = "(re-run with --debug for the full traceback)"


def _debug_enabled(ctx):
    return bool(ctx.find_root().params.get("debug", False))


# POLICY: every command routes through this boundary, which surfaces the
# exception's own message -- no sanitizing, summarizing, or redacting. The one
# normalization is outer whitespace: it is trimmed so the appended hint lands on
# the line immediately after the message (and so a whitespace-only message
# counts as blank). The SDK raises bare `Exception`/`ValueError` as its normal
# error-reporting mechanism (`process_failure` in praetorian_cli/sdk/chariot.py,
# praetorian_cli/sdk/entities/*.py), so that message IS the user-facing text.
#
# WHERE TO CHANGE: classification is ENG-6570, redaction is ENG-6781 -- neither
# here. Nor is this the only egress path: praetorian_cli/sdk/mcp_server.py
# returns `str(e)` to its caller, and the SDK is a public library surface.
def _error_message(exc):
    """Surface the exception's own message, plus the `--debug` hint.

    Falls back to the exception's type name when its message is blank.
    """
    message = str(exc).strip() or type(exc).__name__
    return f"{message}\n{DEBUG_HINT}"


def handle_error(func):
    @wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except click.ClickException:
            raise
        except click.Abort:
            raise
        except click.exceptions.Exit:
            raise
        except CancelledError:
            raise
        except Exception as exc:
            if _debug_enabled(ctx):
                raise
            raise click.ClickException(_error_message(exc)) from exc

    return wrapper


# POLICY: the update advisory is best-effort. It is skipped when the session is
# not interactive, when the opt-out env var is set, and when a group callback is
# merely delegating to a subcommand; it reaches pypi.org at most once per TTL,
# carries no command context (no argv, profile, account, or custom headers), and
# fails open -- no ordinary failure of it changes a command outcome. The cache is
# private where the platform enforces POSIX modes: 0700 directory, 0600 file,
# atomic same-directory replace.
#
# WHERE TO CHANGE: cadence, opt-out, endpoint, and timeout are the constants
# below; the advisory itself is `_check_for_update`.
UPDATE_CHECK_CACHE_TTL_SECONDS = 24 * 60 * 60
UPDATE_CHECK_DISABLE_ENV = "PRAETORIAN_CLI_DISABLE_UPDATE_CHECK"
UPDATE_CHECK_DISABLE_VALUES = frozenset({"1", "true", "yes", "on"})
UPDATE_CHECK_NON_INTERACTIVE_ENV = ("CI", "GITHUB_ACTIONS")
UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS = 60
UPDATE_CHECK_TIMEOUT_SECONDS = 2
UPDATE_CHECK_URL = "https://pypi.org/pypi/praetorian-cli/json"


def _session_is_interactive():
    """True only when a human is plausibly watching this invocation.

    BOTH streams must be a terminal. An stderr-only gate does not hold: in
    `guard list assets | jq` only stdout is redirected, so stderr stays a tty
    and the advisory still fires -- the piped, scripted, high-volume case whose
    cadence this is supposed to stop leaking. `CI`/`GITHUB_ACTIONS`/`TERM=dumb`
    cover the runners that allocate a pty anyway.
    """
    try:
        if not (sys.stdout.isatty() and sys.stderr.isatty()):
            return False
    except Exception:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return not any(os.environ.get(name) for name in UPDATE_CHECK_NON_INTERACTIVE_ENV)


def _update_check_disabled():
    """Accept any conventional truthy value, not only `1`.

    This is a privacy opt-out: a user who exports `=true` and still gets network
    requests has been silently overruled by a parsing detail.
    """
    return os.environ.get(UPDATE_CHECK_DISABLE_ENV, "").strip().lower() in UPDATE_CHECK_DISABLE_VALUES


def _delegating_to_subcommand():
    """True when this callback is a group about to invoke a subcommand.

    Click runs a group callback BEFORE its subcommand (measured), so an advisory
    printed here precedes the work the user asked for, and still prints when that
    subcommand goes on to fail. The leaf command runs its own check, so skipping
    here loses nothing -- and it needs no hand-maintained command list.
    """
    ctx = click.get_current_context(silent=True)
    return ctx is not None and ctx.invoked_subcommand is not None


def _update_check_cache_path():
    cache_home = os.environ.get("XDG_CACHE_HOME")
    # POLICY: a relative `XDG_CACHE_HOME` is ignored, as the XDG base-directory
    # spec requires. Honouring one resolves the cache against the current working
    # directory, so every invocation from a different directory sees a cold cache
    # and re-probes. An empty value is falsy and already falls back here.
    if cache_home and not Path(cache_home).is_absolute():
        cache_home = None
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "praetorian-cli" / "update-check.json"


def _path_is_owned_by_effective_user(path):
    """True when `path` belongs to us -- and on platforms that have no uids.

    POLICY: `os.geteuid` is POSIX-only, so its absence must read as "owned"
    rather than take the advisory down; an unguarded POSIX-only call has done
    the latter here once already.
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return True
    return path.stat().st_uid == geteuid()


def _create_update_refresh_marker(marker_path):
    """True only for the call that created the marker. Never raises."""
    try:
        os.close(os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except OSError:
        return False


def _claim_update_refresh_marker(cache_path):
    """The marker path when this invocation may refresh, otherwise None.

    POLICY: exactly one of N simultaneous invocations refreshes. The throttle
    record cannot deliver that on its own -- all N read the stale cache before
    any of them writes -- so the claim is an exclusive create. `O_EXCL` is
    atomic on POSIX and Windows alike, which is why it is the mechanism here
    instead of `fcntl`/`flock`. Losing the claim skips the REFRESH only.

    WHERE TO CHANGE: the stale window is
    `UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS`. A marker older than that is
    unlinked and the claim re-attempted exactly once, so a process killed while
    holding one cannot wedge refreshes for good. Any `OSError` anywhere here
    means "did not win".
    """
    marker_path = cache_path.with_name(cache_path.name + ".refresh")
    if _create_update_refresh_marker(marker_path):
        return marker_path
    try:
        if time.time() - os.stat(marker_path).st_mtime <= UPDATE_CHECK_REFRESH_MARKER_STALE_SECONDS:
            return None
        os.unlink(marker_path)
    except OSError:
        return None
    return marker_path if _create_update_refresh_marker(marker_path) else None


def _release_update_refresh_marker(marker_path):
    """Best-effort unlink. Never raises: every caller is already in a `finally`."""
    try:
        os.unlink(marker_path)
    except OSError:
        pass


def _parse_version(raw):
    """A `Version`, or None when the value is absent or unparseable.

    Returning None rather than raising is what keeps a malformed PyPI payload
    from killing the advisory through the fail-open arm (measured: an
    unparseable release key took the advisory from 0 to 1). It does not shorten
    a blackout: a fresh entry short-circuits the refresh whether or not its
    version parsed, and such an entry stays silent until its TTL expires -- at
    which point it does recover.
    """
    if not isinstance(raw, str):
        return None
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def _read_update_check_cache(cache_path):
    """`(checked_at, latest_version_or_None)`, or None when there is no usable record.

    A record with a null or unparseable version is still returned: it throttles.
    """
    try:
        with open(cache_path, encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        checked_at = cache["checked_at"]
        if isinstance(checked_at, bool) or not isinstance(checked_at, (int, float)):
            return None
        return checked_at, _parse_version(cache.get("latest_version"))
    except (KeyError, OSError, TypeError, ValueError):
        return None


def _update_check_cache_is_fresh(cached, now):
    """True when `cached` is a usable record still inside the TTL.

    POLICY: a `checked_at` in the future is stale, not fresh, so a bad clock
    cannot pin a stale answer forever.
    """
    return cached is not None and 0 <= now - cached[0] < UPDATE_CHECK_CACHE_TTL_SECONDS


def _prepare_update_check_cache_dir(cache_path):
    """Create the cache directory and lock it to 0700. True only when writing there is safe.

    POLICY: the LEAF directory only -- the `praetorian-cli` directory this
    creates. A symlinked `~/.cache` is a legitimate, common dotfile setup and
    must keep working, so do NOT widen this to ancestors. Following a symlinked
    leaf would chmod and write inside whatever directory someone else pointed it
    at, and a path we did not create is only ours to repair when it is a
    directory we own.

    WHERE TO CHANGE: this runs before the refresh marker is claimed (the marker
    needs a directory to be created in) and again inside
    `_write_update_check_cache`, which validates on its own terms rather than
    trusting its caller.
    """
    try:
        parent = cache_path.parent
        if parent.is_symlink():
            return False
        try:
            parent.mkdir(parents=True, mode=0o700)
            created = True
        except FileExistsError:
            created = False
        if not created and not (parent.is_dir() and _path_is_owned_by_effective_user(parent)):
            return False
        # mkdir's mode is masked by umask; the chmod is what guarantees the mode.
        parent.chmod(0o700)
        return True
    except CancelledError:
        raise
    except Exception:
        return False


def _write_update_check_cache(cache_path, checked_at, latest_version):
    """Record an attempt. True on success, False when this environment cannot.

    The contract, spelled out because this one write is load-bearing for three
    unrelated properties:

    * It VALIDATES THE DESTINATION before touching it, through
      `_prepare_update_check_cache_dir`, whatever its caller already did.
    * It lets NOTHING ESCAPE. No descriptor and no `mkstemp` leftover survives
      any failure path, including a failure raised between `mkstemp` and
      `os.fdopen`.
    * It is NO PART of the exclusion between concurrent refreshes. That is
      `_claim_update_refresh_marker`, and `_check_for_update` claims it BEFORE
      calling this -- so reaching this function at all already means this
      invocation is the one refreshing.
    * `False` means "this environment cannot be throttled, so do not probe".
      Returns rather than raises: the caller treats a failed write as a
      control-flow signal (stay off the network), not as an error to swallow.
    """
    try:
        parent = cache_path.parent
        if not _prepare_update_check_cache_dir(cache_path):
            return False
        # Same directory as the destination, so `os.replace` is an atomic rename.
        # `mkstemp` creates the file 0600 regardless of umask (measured at
        # `umask 0000`), which is why no `os.fchmod` follows it: `os.fchmod` is
        # POSIX-only, and on Windows its AttributeError was swallowed by the
        # fail-open arm -- taking the whole advisory down with it, every run.
        fd, temp_name = tempfile.mkstemp(dir=parent)
        temp_path = Path(temp_name)
        try:
            # `os.fdopen` takes ownership of the descriptor only once it returns,
            # so a failure inside it leaves the descriptor with no owner at all;
            # the `finally` below reclaims the path, never the descriptor.
            # `BaseException`, because a KeyboardInterrupt landing here leaks
            # identically.
            try:
                temp_file = os.fdopen(fd, "w", encoding="utf-8")
            except BaseException:
                os.close(fd)
                raise
            with temp_file:
                json.dump(
                    {
                        "checked_at": checked_at,
                        "latest_version": None if latest_version is None else str(latest_version),
                    },
                    temp_file,
                )
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, cache_path)
            cache_path.chmod(0o600)
        finally:
            temp_path.unlink(missing_ok=True)
        return True
    except CancelledError:
        raise
    except Exception:
        return False


def _fetch_latest_version():
    """PyPI's own latest STABLE release, or None when the payload is unusable.

    `info.version` rather than `max(Version(r) for r in releases)`: the max over
    release keys ranks prereleases above stable ones (2.0.0rc1 over 1.0.0), and a
    single unparseable key raises `InvalidVersion` into the fail-open arm.
    """
    response = requests.get(UPDATE_CHECK_URL, timeout=UPDATE_CHECK_TIMEOUT_SECONDS)
    response.raise_for_status()
    return _parse_version(response.json()["info"]["version"])


def _check_for_update():
    try:
        if _update_check_disabled():
            return
        if not _session_is_interactive():
            return
        if _delegating_to_subcommand():
            return
        now = time.time()
        cache_path = _update_check_cache_path()
        cached = _read_update_check_cache(cache_path)
        latest = cached[1] if cached is not None else None
        if not _update_check_cache_is_fresh(cached, now):
            # The marker below is created IN the cache directory, so the directory
            # has to exist and be trustworthy first. Failing to prepare it is the
            # same signal a failed record write is: an environment whose probe
            # rate we cannot limit is one we must not probe.
            if not _prepare_update_check_cache_dir(cache_path):
                return
            # POLICY: the throttle record orders SEQUENTIAL invocations; it does
            # nothing for simultaneous ones, which all read the stale cache before
            # any of them writes. The marker is what makes exactly one of them
            # refresh, and it is claimed BEFORE that record is written -- claimed
            # after, the only record a late arrival could find would be its own,
            # and it would refresh again. Losing the claim skips the REFRESH only:
            # control falls through to the comparison below, so a version already
            # known is still advertised.
            marker_path = _claim_update_refresh_marker(cache_path)
            if marker_path is not None:
                try:
                    # A peer that refreshed while we queued for the claim wrote
                    # its record before fetching, so it is readable here and this
                    # invocation stands down exactly as a lost claim does. The
                    # clock is read again rather than reused: `now` was sampled
                    # before the claim, so a peer record written after it would
                    # score as a future timestamp and read as stale.
                    refreshed = _read_update_check_cache(cache_path)
                    if _update_check_cache_is_fresh(refreshed, time.time()):
                        latest = refreshed[1]
                    # Record the attempt BEFORE making it, so EVERY way a refresh
                    # can fail is throttled by the same record -- network and HTTP
                    # errors, an unparseable payload, and the environments where
                    # the cache cannot be written at all (a read-only filesystem,
                    # a cache directory owned by another user). A file-based cache
                    # written only on success cannot throttle the case where the
                    # file cannot be written, which is how this reached pypi.org
                    # on every single invocation. The previous known version rides
                    # along, so a failed refresh keeps advertising what we already
                    # knew.
                    elif not _write_update_check_cache(cache_path, now, latest):
                        return
                    else:
                        try:
                            fetched = _fetch_latest_version()
                        except CancelledError:
                            raise
                        except Exception:
                            fetched = None
                        if fetched is not None:
                            latest = fetched
                            _write_update_check_cache(cache_path, now, latest)
                finally:
                    _release_update_refresh_marker(marker_path)
        if latest is None:
            return
        local = Version(version('praetorian-cli'))
        if latest > local:
            click.echo(f'A new version of praetorian-cli is available: {latest}', err=True)
            click.echo(f'You are currently running {local}.', err=True)
            click.echo('To upgrade, run "pip install --upgrade praetorian-cli".', err=True)
    except CancelledError:
        raise
    # `Exception`, not a bare `except`: KeyboardInterrupt and SystemExit derive
    # from BaseException, so they keep propagating instead of being swallowed.
    except Exception:
        pass


def upgrade_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        _check_for_update()
        return result

    return wrapper

def cli_handler(func):
    func = click.pass_obj(func)
    func = handle_error(func)
    func = upgrade_check(func)
    return func


def list_params(filter_by, has_details=True, has_filter=True, has_type=False):
    def decorator(func):
        func = pagination(func)
        func = cli_handler(func)
        if has_filter:
            func = click.option('-f', '--filter', default='', help=f'Filter by {filter_by}')(func)
        if has_details:
            func = click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')(func)
        if has_type:
            func = click.option('-t', '--type', "model_type", default='', help='Select only a subset by type')(func)
        return func

    return decorator


def pagination(func):
    func = click.option('-o', '--offset', default=0, help='List results from an offset')(func)
    func = click.option('-p', '--page', type=click.Choice(('first', 'all')), default='first',
                        help='Pagination mode. "all" pages up to 10,000 pages.', show_default=True)(func)
    return func

def praetorian_only(func):
    @wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        if not ctx.obj.is_praetorian_user():
            error("This option is limited to Praetorian engineers only. Please contact your Praetorian representative for assistance.")
        return func(*args, **kwargs)
    return wrapper
