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
    """ Add a collaborator account to your account

    This allows them to assume access into your account
    and perform actions on your behalf.

    \b
    Arguments:
        - NAME: their email address



    \b
    Example usages:
        - praetorian chariot link account john@praetorian.com
    """
    chariot.accounts.add_collaborator(username)
