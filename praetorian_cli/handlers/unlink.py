import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
@cli_handler
def unlink(ctx):
    """Unlink an account or integration from Chariot"""
    pass


@unlink.command('account')
@click.argument('account_id')
@cli_handler
def unlink_account(controller, account_id):
    """ Unlink an account """
    controller.unlink(account_id, "")
