import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, status_options
from praetorian_cli.handlers.utils import Status


@chariot.group()
@cli_handler
def update(ctx):
    """Update a resource in Chariot"""
    pass


@update.command('asset', help='Update an asset\n\nKEY is the key of the asset')
@click.argument('key', required=True)
@status_options(Status['asset'], 'asset')
def asset(controller, key, status):
    controller.update('asset', dict(key=key, status=status))


@update.command('risk', help='Update a risk\n\nKEY is the key of the risk')
@click.argument('key', required=True)
@status_options(Status['risk'], 'risk')
@click.option('-comment', '--comment', default='', help='Comment for the risk')
def risk(controller, key, status, comment):
    controller.update('risk', dict(key=key, status=status, comment=comment))
