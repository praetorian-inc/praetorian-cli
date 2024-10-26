import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def unlink():
    """ Remove a collaborator from your account """
    pass


@unlink.command()
@cli_handler
@click.argument('username')
def account(chariot, username):
    """ Remove a collaborator account from your account. This will
    revoke their access to your account.

    Arguments:
        - NAME: Their email address.

    \b
    Example usages:
        - praetorian chariot unlink account john@praetorian.com
    """
    chariot.accounts.delete_collaborator(username)
