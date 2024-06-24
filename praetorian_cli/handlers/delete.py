import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
@cli_handler
def delete(ctx):
    """Delete a resource from Chariot"""
    pass


def delete_command(item):
    @delete.command(item, help=f"Delete {item}")
    @click.argument('key', required=True)
    @cli_handler
    def command(controller, key):
        if item == 'attribute':
            resp = controller.delete('asset/attribute', key)
        else:
            resp = controller.delete(item, key)
        print(f"Key: {key} \nDeleted successfully")


for item in ['seed', 'attribute']:
    delete_command(item)
