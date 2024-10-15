import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def get():
    """ Get entity details from Chariot """
    pass


@get.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-d', '--details', is_flag=True, help='Get attributes of the asset')
def asset(chariot, key, details):
    """ Get asset details """
    print_json(chariot.assets.get(key, details))


@get.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-d', '--details', is_flag=True, help='Get attributes of the risk')
def risk(chariot, key, details):
    """ Get risk details """
    print_json(chariot.risks.get(key, details))


@get.command()
@cli_handler
@click.argument('key', required=True)
def attribute(chariot, key):
    """ Get asset details """
    print_json(chariot.attributes.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def account(chariot, key):
    """ Get account (collaborator or authorized master account) details """
    print_json(chariot.accounts.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def integration(chariot, key):
    """ Get integration details """
    print_json(chariot.integrations.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def job(chariot, key):
    """ Get job details """
    print_json(chariot.jobs.get(key))


@get.command()
@cli_handler
@click.argument('name')
@click.option('-p', '--path', default=os.getcwd(), help='Download path. Default: save to current directory')
def file(chariot, name, path):
    """ Download a file using key or name."""
    if name.startswith('#'):
        downloaded_filepath = chariot.files.get(name.split('#')[-1], path)
    else:
        downloaded_filepath = chariot.files.get(name, path)
    print(f'Saved file at {downloaded_filepath}')


@get.command()
@cli_handler
@click.argument('name')
@click.option('-path', '--path', default=os.getcwd(), help='Download path. Default: save to current directory')
def definition(chariot, name, path):
    """ Download a definition using the risk name. """
    downloaded_path = chariot.definitions.get(name, path)
    click.echo(f'Saved definition at {downloaded_path}')


@get.command()
@cli_handler
def webhook(chariot):
    """ Get the webhook URL """
    if chariot.webhook.get_record():
        click.echo(chariot.webhook.get_url())
    else:
        click.echo('No existing webhook.')
