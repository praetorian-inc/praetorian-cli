import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import AssetPriorities
from praetorian_cli.sdk.model.globals import Risk


@chariot.group()
def update():
    """ Update an entity in Chariot """
    pass


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-p', '--priority', type=click.Choice(AssetPriorities.keys()), required=True,
              help='The priority of the asset')
def asset(chariot, key, priority):
    """
    Update an asset

    KEY is the key of the asset
    """
    chariot.assets.update(key, AssetPriorities[priority])


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Risk]), help=f'Status of the risk')
@click.option('-c', '--comment', default='', help='Comment for the risk')
def risk(chariot, key, status, comment):
    """
    Update a risk

    KEY is the key of the risk
    """
    chariot.risks.update(key, status, comment)
