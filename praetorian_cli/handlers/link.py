import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
@cli_handler
def link(ctx):
    """Link an account or integration to Chariot"""
    pass


@link.command('chariot')
@cli_handler
@click.argument('username')
def link_account(controller, username):
    """ Link another Chariot account to yours """
    controller.link_account(username, config={})
