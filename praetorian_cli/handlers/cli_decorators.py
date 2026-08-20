from concurrent.futures import CancelledError
from functools import wraps
from importlib.metadata import version

import click
import requests
from packaging.version import Version

from praetorian_cli.handlers.utils import error


DEBUG_HINT = "(re-run with --debug for the full traceback)"


def _debug_enabled(ctx):
    return bool(ctx.find_root().params.get("debug", False))


# POLICY: every command routes through this boundary, which passes the
# exception's message through unchanged -- no sanitizing, summarizing, or
# redacting. The SDK raises bare `Exception`/`ValueError` as its normal
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


def upgrade_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            response = requests.get('https://pypi.org/pypi/praetorian-cli/json', timeout=3)
            pypi = sorted([Version(v) for v in list(response.json()['releases'].keys())])[-1]
            local = Version(version('praetorian-cli'))
            if pypi > local:
                click.echo(f'A new version of praetorian-cli is available: {pypi}', err=True)
                click.echo(f'You are currently running {local}.', err=True)
                click.echo('To upgrade, run "pip install --upgrade praetorian-cli".', err=True)
        except:
            # Silently fail if we can't check for updates
            # This preserves the main functionality even if update checks fail
            pass
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
