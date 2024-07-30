import datetime

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.command('version')
@cli_handler
def version(controller):
    """ Retrieve version information of Chariot """
    v = controller.version()
    click.echo(f'Chariot backend version: {v["backend_hash"]} ({datetime.date.fromtimestamp(v["backend_date"])})')
