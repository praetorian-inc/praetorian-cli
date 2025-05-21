import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.sdk.model.globals import Risk


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
@click.option('-s', '--status', default='DIO', type=click.Choice([s.value for s in Risk]),
              help='A risk status to provide the sub-state for deleting.')
@click.option('-c', '--comment', default='', help='Optional comment for the delete')
def risk(chariot, key, status, comment):
    """ Delete a risk

    \b
    Arguments:
        - KEY: the key of an existing risk

    \b
    Example usage:
        - praetorian chariot delete risk "#risk#example.com#CVE-2024-23049" --status DIO
    """
    chariot.risks.delete(key, status, comment)


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


@delete.command()
@click.argument('filepath', required=True)
@cli_handler
def file(chariot, filepath):
    """ Delete a file

    \b
    Arguments:
        - FILEPATH: The Chariot file path

    \b
    Example usage:
        - praetorian chariot delete file "home/report-dec-2024.pdf"
    """
    chariot.files.delete(filepath)


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


@delete.command()
@cli_handler
@click.argument('name', required=True)
def setting(chariot, name):
    """ Delete a setting

    \b
    Arguments:
        - NAME: the name of an existing setting

    \b
    Example usage:
        - praetorian chariot delete setting "rate-limit"
    """
    chariot.settings.delete(name)


@delete.command()
@cli_handler
@click.argument('name', required=True)
@click.option('-e', '--entry', required=False, help='Optional key to delete from the configuration. If not provided, the entire configuration will be deleted.')
@praetorian_only
def configuration(chariot, name, entry):
    """ Delete a configuration or a specific entry from a configuration

    \b
    Arguments:
        - NAME: the name of an existing configuration

    \b
    Example usage:
        - praetorian chariot delete configuration "nuclei"
        - praetorian chariot delete configuration "nuclei" --entry extra-tags
    """
    if entry:
        # Delete a specific entry from the configuration
        from praetorian_cli.sdk.model.utils import configuration_key
        config_key = configuration_key(name)
        existing_config = chariot.configurations.get(config_key)
        
        if not existing_config:
            click.echo(f"Configuration '{name}' not found")
            return
            
        current_value = existing_config.get('value', {})
        if isinstance(current_value, str):
            try:
                import json
                current_value = json.loads(current_value)
            except:
                current_value = {}
                
        if entry in current_value:
            del current_value[entry]
            chariot.configurations.add(name, current_value)
            click.echo(f"Entry '{entry}' deleted from configuration '{name}'")
        else:
            click.echo(f"Entry '{entry}' not found in configuration '{name}'")
    else:
        # Delete the entire configuration
        chariot.configurations.delete(name)
