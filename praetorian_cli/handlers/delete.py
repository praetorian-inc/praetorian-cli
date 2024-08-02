import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import Asset


@chariot.group()
@cli_handler
def delete(ctx):
    """Delete a resource from Chariot"""
    pass


@delete.command('asset')
@click.argument('key', required=True)
@cli_handler
def delete_asset(controller, key):
    """
    Delete asset

    KEY is the key of an existing asset
    """
    controller.update('asset', dict(key=key, status=Asset.DELETED.value))


def delete_command(item):
    @delete.command(item, help=f"Delete {item}")
    @click.argument('key', required=True)
    @cli_handler
    def command(controller, key):
        controller.delete(item, key)
        print(f"Key: {key} \nDeleted successfully")


for item in ['attribute', 'file']:
    delete_command(item)


# Special command for deleting your account and all related information.
@chariot.command('purge')
@cli_handler
def purge(controller):
    """Delete account and all related information"""
    if click.confirm("This will delete all your data and revoke access, are you sure?", default=False):
        controller.purge()
    else:
        click.echo("Operation cancelled")
        return
    print("Account deleted successfully")
