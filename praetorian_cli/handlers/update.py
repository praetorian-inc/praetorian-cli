import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import AssetPriorities, Risk


@chariot.group()
@cli_handler
def update(ctx):
    """Update a resource in Chariot"""
    pass


@update.command('asset')
@click.argument('key', required=True)
@click.option('--priority', type=click.Choice(AssetPriorities.keys()), required=True, help='The priority of the asset')
@cli_handler
def asset(controller, key, priority):
    """
    Update an asset

    KEY is the key of the asset
    """
    controller.update('asset', dict(key=key, status=AssetPriorities[priority]))


@update.command('risk')
@click.argument('key', required=True)
@click.option('-status', '--status', type=click.Choice([s.value for s in Risk]), help=f'Status of the risk')
@click.option('-comment', '--comment', default='', help='Comment for the risk')
@cli_handler
def risk(controller, key, status, comment):
    """
    Update a risk

    KEY is the key of the risk
    """
    controller.update('risk', dict(key=key, status=status, comment=comment))
