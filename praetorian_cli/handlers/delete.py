import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def delete():
    """ Delete an entity from Chariot """
    pass


@delete.command()
@click.argument('key', required=True)
@cli_handler
def asset(chariot, key):
    """ Delete an asset

    \b
    Arguments:
        - KEY: the key of an existing asset

    \b
    Example usage:
        - praetorian chariot delete asset "#asset#www.example.com#1.2.3.4"
    """
    chariot.assets.delete(key)


@delete.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-c', '--comment', default='', help='Optional comment for the delete')
def risk(chariot, key, comment):
    """ Delete a risk

    \b
    Arguments:
        - KEY: the key of an existing risk

    \b
    Example usage:
        - praetorian chariot delete risk "#risk#example.com#CVE-2024-23049"
    """
    chariot.risks.delete(key, comment)


@delete.command()
@cli_handler
@click.argument('key', required=True)
def attribute(chariot, key):
    """ Delete an attribute

    \b
    Arguments:
        - KEY: the key of an existing attribute

    \b
    Example usage:
        - praetorian chariot delete attribute "#attribute#source#kev#risk#api.example.com#CVE-2024-23049"
    """
    chariot.attributes.delete(key)


@delete.command()
@cli_handler
def webhook(chariot):
    """ Delete webhook

    Example usage:
        - praetorian chariot delete webhook
    """
    if chariot.webhook.get_record():
        chariot.webhook.delete()
        click.echo('Webhook successfully deleted.')
    else:
        click.echo('No webhook previously exists.')


@delete.command()
@click.argument('key', required=True)
@cli_handler
def seed(chariot, key):
    """ Delete a seed

    \b
    Arguments:
        - KEY: the key of an existing seed

    \b
    Example usage:
        - praetorian chariot delete seed "#seed#domain#example.com"
    """
    chariot.seeds.delete(key)


# Special command for deleting your account and all related information.
@chariot.command()
@cli_handler
def purge(controller):
    """ Delete account and all related information

    Example usage:
        - praetorian chariot purge
    """
    if click.confirm('This will delete all your data and revoke access, are you sure?', default=False):
        controller.purge()
    else:
        click.echo('Purge cancelled')
        return
    click.echo('Account deleted successfully')
