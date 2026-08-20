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
from packaging.version import Version

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


# POLICY: the update advisory is best-effort. It is skipped when stderr is not a
# TTY and when the opt-out env var is set, reaches pypi.org at most once per TTL,
# carries no command context (no argv, profile, account, or custom headers), and
# fails open -- no command outcome depends on it. The cache is private by
# construction: 0700 directory, 0600 file, atomic same-directory replace.
#
# WHERE TO CHANGE: cadence, opt-out, endpoint, and timeout are the constants
# below; the advisory itself is `_check_for_update`.
UPDATE_CHECK_CACHE_TTL_SECONDS = 24 * 60 * 60
UPDATE_CHECK_DISABLE_ENV = "PRAETORIAN_CLI_DISABLE_UPDATE_CHECK"
UPDATE_CHECK_TIMEOUT_SECONDS = 2
UPDATE_CHECK_URL = "https://pypi.org/pypi/praetorian-cli/json"


def _stderr_is_interactive():
    try:
        return bool(sys.stderr.isatty())
    except Exception:
        return False


def _update_check_disabled():
    return os.environ.get(UPDATE_CHECK_DISABLE_ENV) == "1"


def _update_check_cache_path():
    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "praetorian-cli" / "update-check.json"


def _fresh_cached_version(cache_path, now):
    try:
        with open(cache_path, encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        age = now - cache["checked_at"]
        # A `checked_at` in the future is stale, not fresh, so a bad clock cannot
        # pin a stale answer forever.
        if 0 <= age < UPDATE_CHECK_CACHE_TTL_SECONDS:
            return cache["latest_version"]
    except (KeyError, OSError, TypeError, ValueError):
        return None
    return None


def _write_update_check_cache(cache_path, checked_at, latest_version):
    parent = cache_path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir's mode is masked by umask; the chmod is what guarantees the mode.
    parent.chmod(0o700)
    # Same directory as the destination, so `os.replace` is an atomic rename.
    # `mkstemp` already creates the file 0600; the `fchmod` reinforces that.
    fd, temp_name = tempfile.mkstemp(dir=parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            os.fchmod(temp_file.fileno(), 0o600)
            json.dump({"checked_at": checked_at, "latest_version": latest_version}, temp_file)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, cache_path)
        cache_path.chmod(0o600)
    finally:
        temp_path.unlink(missing_ok=True)


def _check_for_update():
    try:
        if not _stderr_is_interactive():
            return
        if _update_check_disabled():
            return
        now = time.time()
        cache_path = _update_check_cache_path()
        latest_version = _fresh_cached_version(cache_path, now)
        if latest_version is None:
            response = requests.get(UPDATE_CHECK_URL, timeout=UPDATE_CHECK_TIMEOUT_SECONDS)
            response.raise_for_status()
            latest_version = str(max(Version(r) for r in response.json()['releases']))
            _write_update_check_cache(cache_path, now, latest_version)
        pypi = Version(latest_version)
        local = Version(version('praetorian-cli'))
        if pypi > local:
            click.echo(f'A new version of praetorian-cli is available: {pypi}', err=True)
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
