import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def get():
    """ Get entity details from Chariot """
    pass


@get.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-d', '--details', is_flag=True, help='Further retrieve the attributes and associated risks of the asset')
def asset(chariot, key, details):
    """ Get asset details

    \b
    Argument:
        - KEY: the key of an existing asset

    \b
    Example usages:
        - praetorian chariot get asset "#asset#api.example.com#1.2.3.4"
        - praetorian chariot get asset "#asset#api.example.com#1.2.3.4" --details
    """
    print_json(chariot.assets.get(key, details))


@get.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-d', '--details', is_flag=True, help='Further retrieve the attributes and affected assets of the risk')
def risk(chariot, key, details):
    """ Get risk details

    \b
    Argument:
        - KEY: the key of an existing risk

    \b
    Example usages:
        - praetorian chariot get risk "#risk#api.example.com#CVE-2024-23049"
        - praetorian chariot get risk "#risk#api.example.com#CVE-2024-23049" --details
     """
    print_json(chariot.risks.get(key, details))


@get.command()
@cli_handler
@click.argument('key', required=True)
def attribute(chariot, key):
    """ Get attribute details

    \b
    Argument:
        - KEY: the key of an existing attribute

    \b
    Example usage:
        - praetorian chariot get attribute "#attribute#source#kev#risk#api.example.com#CVE-2024-23049"
    """
    print_json(chariot.attributes.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def account(chariot, key):
    """ Get account (collaborator or authorized master account) details

    \b
    Argument:
        - KEY: key of an existing account

    \b
    Example usage:
        - praetorian chariot get account "#account#peter@example.com#john@praetorian.com"
    """
    print_json(chariot.accounts.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def integration(chariot, key):
    """ Get integration details

    \b
    Argument:
        - KEY: key of an existing integration connection

    \b
    Example usage:
        - praetorian chariot get integration "#account#john@praetorian.com#azure#556bee78-30d0-4a4c-8e4f-8ac2e19ce3d5"
    """
    print_json(chariot.integrations.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
def job(chariot, key):
    """ Get job details

    \b
    Argument:
        - KEY: key of an existing, recently scheduled, job

    \b
    Example usage:
        - praetorian chariot get job "#job#api.example.com#1.2.3.4#portscan"
    """
    print_json(chariot.jobs.get(key))


@get.command()
@cli_handler
@click.argument('name')
@click.option('-p', '--path', default=os.getcwd(), help='Download path. Default: save to current directory')
def file(chariot, name, path):
    """ Download a file using key or name

    \b
    Argument:
        - NAME: key or name of an existing file

    \b
    Example usage:
        - praetorian chariot get file "#file#proofs/example.azurewebsites.net/jira-unauthenticated-user-picker"
        - praetorian chariot get file "proofs/example.azurewebsites.net/jira-unauthenticated-user-picker"
        - praetorian chariot get file "proofs/example.azurewebsites.net/jira-unauthenticated-user-picker" --path ~/Downloads
    """
    if name.startswith('#'):
        downloaded_filepath = chariot.files.save(name.split('#')[-1], path)
    else:
        downloaded_filepath = chariot.files.save(name, path)
    click.echo(f'Saved file at {downloaded_filepath}')


@get.command()
@cli_handler
@click.argument('name')
@click.option('-path', '--path', default=os.getcwd(), help='Download path. Default: save to current directory')
def definition(chariot, name, path):
    """ Download a definition using the risk name

    \b
    Argument:
        - NAME: name of a risk

    \b
    Example usage:
        - praetorian chariot get definition jira-unauthenticated-user-picker
        - praetorian chariot get definition CVE-2024-23049
     """
    downloaded_path = chariot.definitions.get(name, path)
    click.echo(f'Saved definition at {downloaded_path}')


@get.command()
@cli_handler
def webhook(chariot):
    """ Get the webhook URL

    \b
    Example usage:
        - praetorian chariot get webhook
    """
    if chariot.webhook.get_record():
        click.echo(chariot.webhook.get_url())
    else:
        click.echo('No existing webhook.')


@get.command()
@cli_handler
@click.argument('key', required=True)
def seed(chariot, key):
    """ Get seed details

    \b
    Argument:
        - KEY: the key of an existing pre-seed

    \b
    Example usages:
        - praetorian chariot get preseed "#preseed#domain#example.com"
    """
    print_json(chariot.seeds.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-d', '--details', is_flag=True, help='Further retrieve the details of the pre-seed')
def preseed(chariot, key, details):
    """ Get pre-seed details

    \b
    Argument:
        - KEY: the key of an existing preseed

    \b
    Example usages:
        - praetorian chariot get preseed "#preseed#whois+company#Example Companys#example company"
        - praetorian chariot get preseed "#preseed#whois+company#Example Companys#example company" --details
    """
    print_json(chariot.preseeds.get(key, details))


@get.command()
@cli_handler
@click.argument('key', required=True)
def setting(chariot, key):
    """ Get setting details

    \b
    Argument:
        - KEY: the key of an existing setting

    \b
    Example usage:
        - praetorian chariot get setting "#setting#rate-limit"
    """
    print_json(chariot.settings.get(key))


@get.command()
@cli_handler
@click.argument('key', required=True)
@praetorian_only
def configuration(chariot, key):
    """ Get configuration details

    \b
    Argument:
        - KEY: the key of an existing configuration

    \b
    Example usage:
        - praetorian chariot get configuration "#configuration#nuclei"
    """
    print_json(chariot.configurations.get(key))


@get.command()
@cli_handler
@click.argument('credential_id', required=True)
@click.option('--category', default='env-integration', help='The category of the credential (e.g., integration, cloud)')
@click.option('--type', default='default', help='The type of credential (e.g., aws, gcp, azure, static, ssh_key, json)')
@click.option('--format', default='token', help='The format of the credential response')
@click.option('--parameters', nargs=2, multiple=True, help='Additional parameters, as --parameters key value')
def credential(chariot, credential_id, category, type, format, parameters):
    """ Get a specific credential

    Retrieve a specific credential using the credential broker.

    \b
    Argument:
        - CREDENTIAL_ID: the ID of the credential to retrieve

    \b
    Example usages:
        - praetorian chariot get credential aws-prod --category integration --type aws --format json
        - praetorian chariot get credential ssh-key-1 --category cloud --type ssh_key --format pem
    """
    import json
    
    params = {}
    if parameters:
        try:
            params = json.loads(parameters)
        except json.JSONDecodeError:
            click.echo("Error: Invalid JSON format for parameters")
            return
    
    result = chariot.credentials.get(credential_id, category, type, [format], **params)
    output = chariot.credentials.format_output(result)
    click.echo(output)
