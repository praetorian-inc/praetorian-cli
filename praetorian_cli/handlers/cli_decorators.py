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
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "praetorian-cli" / "update-check.json"


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


def _write_update_check_cache(cache_path, checked_at, latest_version):
    """Record an attempt. True on success, False when this environment cannot.

    Returns rather than raises: the caller treats a failed write as a
    control-flow signal (stay off the network), not as an error to swallow.
    """
    try:
        parent = cache_path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir's mode is masked by umask; the chmod is what guarantees the mode.
        parent.chmod(0o700)
        # Same directory as the destination, so `os.replace` is an atomic rename.
        # `mkstemp` creates the file 0600 regardless of umask (measured at
        # `umask 0000`), which is why no `os.fchmod` follows it: `os.fchmod` is
        # POSIX-only, and on Windows its AttributeError was swallowed by the
        # fail-open arm -- taking the whole advisory down with it, every run.
        fd, temp_name = tempfile.mkstemp(dir=parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
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
        # A `checked_at` in the future is stale, not fresh, so a bad clock cannot
        # pin a stale answer forever.
        is_fresh = cached is not None and 0 <= now - cached[0] < UPDATE_CHECK_CACHE_TTL_SECONDS
        if not is_fresh:
            # Record the attempt BEFORE making it, so EVERY way a refresh can
            # fail is throttled by the same record -- network and HTTP errors, an
            # unparseable payload, and the environments where the cache cannot be
            # written at all (a read-only filesystem, a cache directory owned by
            # another user). A file-based cache written only on success cannot
            # throttle the case where the file cannot be written, which is how
            # this reached pypi.org on every single invocation. A cache write we
            # cannot perform is therefore the signal to stay off the network
            # entirely: an environment whose probe rate we cannot limit is one we
            # must not probe. The previous known version rides along, so a failed
            # refresh keeps advertising what we already knew.
            if not _write_update_check_cache(cache_path, now, latest):
                return
            try:
                fetched = _fetch_latest_version()
            except CancelledError:
                raise
            except Exception:
                fetched = None
            if fetched is not None:
                latest = fetched
                _write_update_check_cache(cache_path, now, latest)
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
