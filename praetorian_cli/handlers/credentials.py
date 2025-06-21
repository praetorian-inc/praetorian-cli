import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def credentials():
    """ Manage credentials """
    pass


@credentials.command()
@click.option('--credential-id', required=True, help='The ID of the credential to retrieve')
@click.option('--category', required=True, help='The category of the credential (e.g., integration, cloud)')
@click.option('--type', required=True, help='The type of credential (e.g., aws, gcp, azure, static, ssh_key, json)')
@click.option('--format', required=True, help='The format of the credential response')
@click.option('--parameters', help='Additional parameters as JSON string')
@cli_handler
def get(chariot, credential_id, category, type, format, parameters):
    """ Get a specific credential

    Retrieve a specific credential using the credential broker.

    \b
    Example usages:
        - praetorian chariot credentials get --credential-id aws-prod --category integration --type aws --format json
        - praetorian chariot credentials get --credential-id ssh-key-1 --category cloud --type ssh_key --format pem
    """
    import json
    
    params = {}
    if parameters:
        try:
            params = json.loads(parameters)
        except json.JSONDecodeError:
            click.echo("Error: Invalid JSON format for parameters")
            return
    
    result = chariot.credentials.get(credential_id, category, type, format, **params)
    print_json(result)
