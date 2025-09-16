import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def unlink():
    """ Remove links between resources """
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


@unlink.command('webpage-source')
@cli_handler
@click.argument('webpage_key')
@click.argument('entity_key')
def webpage_source(chariot, webpage_key, entity_key):
    """ Unlink a file or repository from a webpage's source code

    This removes the association between source code files or 
    repositories and webpages.

    \b
    Arguments:
        - WEBPAGE_KEY: The webpage key in format #webpage#{url}
        - ENTITY_KEY: The file or repository key to unlink
                     Format: #file#{path} or #repository#{url}#{name}

    \b
    Example usages:
        - praetorian chariot unlink webpage-source "#webpage#https://example.com" "#file#proofs/scan.txt"
        - praetorian chariot unlink webpage-source "#webpage#https://example.com/login" "#repository#https://github.com/org/repo.git#repo.git"
    """
    result = chariot.webpage.unlink_source(webpage_key, entity_key)
    if result:
        click.echo(f"Successfully unlinked {entity_key} from {webpage_key}")
        if 'artifacts' in result:
            click.echo(f"Webpage now has {len(result['artifacts'])} linked artifacts")
