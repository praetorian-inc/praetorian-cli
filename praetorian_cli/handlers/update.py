import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, status_options
from praetorian_cli.handlers.utils import Status, AssetPriorities


@chariot.group()
@cli_handler
def update(ctx):
    """Update a resource in Chariot"""
    pass


@update.command('asset', help='Update an asset\n\nKEY is the key of the asset')
@click.argument('key', required=True)
@click.option('-priority', '--priority', type=click.Choice(AssetPriorities.keys()),
              required=True, help='The priority of the asset')
@cli_handler
def update_asset_command(controller, key, priority):
    controller.update('asset', dict(key=key, status=AssetPriorities[priority]))


@update.command('risk', help='Update a risk\n\nKEY is the key of the risk')
@click.argument('key', required=True)
@status_options(Status['risk'], 'risk')
@click.option('-comment', '--comment', default='', help='Comment for the risk')
def risk(controller, key, status, comment):
    controller.update('risk', dict(key=key, status=status, comment=comment))
