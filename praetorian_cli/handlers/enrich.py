import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json

TYPES = ['cve']


@chariot.command()
@cli_handler
@click.option('-t', '--type', type=click.Choice(TYPES), help='The type of enrichment', required=True)
@click.argument('id', required=True)
def enrich(chariot, type, id):
    """ Retrieve enrichment data """
    print_json(chariot.enrichment(type, id))
