import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def link():
    """  Add a collaborator to your account """
    pass


@link.command()
@cli_handler
@click.argument('username')
def account(chariot, username):
    """ Add a collaborator account to your account """
    chariot.accounts.add_collaborator(username)
