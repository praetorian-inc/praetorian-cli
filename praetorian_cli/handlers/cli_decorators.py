import traceback
from functools import wraps

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.utils import error


def handle_error(func):
    @wraps(func)
    def handler(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error(str(e), quit=False)
            if chariot.is_debug:
                click.echo(traceback.format_exc())

    return handler


def cli_handler(func):
    func = click.pass_obj(func)
    func = handle_error(func)
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
