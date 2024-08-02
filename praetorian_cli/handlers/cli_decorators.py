from functools import wraps

import click


def handle_api_error(func):
    @wraps(func)
    def handler(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            click.secho(e.args[0], fg='red')

    return handler


def cli_handler(func):
    func = click.pass_obj(func)
    func = handle_api_error(func)
    return func


def list_options(filter_name):
    def decorator(func):
        func = cli_handler(func)
        func = click.option('-f', '--filter', default="", help=f"Filter by {filter_name}")(func)
        func = click.option('-d', '--details', is_flag=True, default=False, help="Show detailed information")(
            func)
        func = page_options(func)
        return func

    return decorator


def page_options(func):
    func = click.option('-o', '--offset', default='', help='List results from an offset')(func)
    func = click.option('-p', '--page', type=click.Choice(('no', 'interactive', 'all')), default='no',
                        help="Pagination mode. 'all' pages up to 100 pages. Default: 'no'")(func)
    return func
