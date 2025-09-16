import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def link():
    """  Link resources to other entities """
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


@link.command('webpage-source')
@cli_handler
@click.argument('webpage_key')
@click.argument('entity_key')
def webpage_source(chariot, webpage_key, entity_key):
    """ Link a file or repository to a webpage as source code

    This associates source code files or repositories with webpages
    to track where webpage content originates from.

    \b
    Arguments:
        - WEBPAGE_KEY: The webpage key in format #webpage#{url}
        - ENTITY_KEY: The file or repository key to link
                     Format: #file#{path} or #repository#{url}#{name}

    \b
    Example usages:
        - praetorian chariot link webpage-source "#webpage#https://example.com" "#file#proofs/scan.txt"
        - praetorian chariot link webpage-source "#webpage#https://example.com/login" "#repository#https://github.com/org/repo.git#repo.git"
    """
    result = chariot.webpage.link_source(webpage_key, entity_key)
    if result:
        click.echo(f"Successfully linked {entity_key} to {webpage_key}")
        if 'artifacts' in result:
            click.echo(f"Webpage now has {len(result['artifacts'])} linked artifacts")
