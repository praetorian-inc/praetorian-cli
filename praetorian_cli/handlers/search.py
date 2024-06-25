import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, page_options, plugins
from praetorian_cli.handlers.utils import paginate


@chariot.command('search')
@cli_handler
@click.option('-term', '--term', help="Enter a search term", required=True)
@click.option('-count', '--count', is_flag=True, help="Return statistics on search")
@click.option('-details', '--details', is_flag=True, help="Return detailed search results")
@page_options
@plugins
def search(controller, term="", count=False, details=False, offset="", page="interactive"):
    """ Query the Chariot data store for arbitrary matches """
    if count:
        print(controller.count(dict(key=term)))
    else:
        paginate(controller, key=term, details=details, offset=offset, page=page)
