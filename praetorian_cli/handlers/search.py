import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, pagination
from praetorian_cli.handlers.utils import render_list_results, print_json, pagination_size


@chariot.command()
@cli_handler
@pagination
@click.option('-t', '--term', help='Enter a search term', required=True)
@click.option('-c', '--count', is_flag=True, default=False, help='Return statistics on search')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
def search(chariot, term, count, details, offset, page):
    """ Query Chariot for arbitrary matches using the search syntax """
    if count:
        print_json(chariot.search.count(term))
    else:
        render_list_results(chariot.search.by_term(term, offset, pagination_size(page)), details)
