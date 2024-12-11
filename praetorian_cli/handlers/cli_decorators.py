import traceback
from functools import wraps
from importlib.metadata import version

import click
import requests
from packaging.version import Version

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.utils import error


def handle_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error(str(e), quit=False)
            if chariot.is_debug:
                click.echo(traceback.format_exc())

    return wrapper


def upgrade_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            response = requests.get('https://pypi.org/pypi/praetorian-cli/json')
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


def list_params(filter_by, has_details=True):
    def decorator(func):
        func = click.option('-f', '--filter', default='', help=f'Filter by {filter_by}')(func)
        func = pagination(func)
        func = cli_handler(func)
        if has_details:
            func = click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')(func)
        return func

    return decorator


def pagination(func):
    func = click.option('-o', '--offset', default='', help='List results from an offset')(func)
    func = click.option('-p', '--page', type=click.Choice(('first', 'all')), default='first',
                        help='Pagination mode. "all" pages up to 1000 pages.', show_default=True)(func)
    return func
