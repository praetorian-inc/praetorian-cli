import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, status_options
from praetorian_cli.handlers.utils import Status


@chariot.group()
@cli_handler
def update(ctx):
    """Update a resource in Chariot"""
    pass


def create_update_command(item_type):
    @update.command(item_type, help=f'Update a {item_type}\n\nKEY is the key of the {item_type}')
    @click.argument('key', required=True)
    @status_options(Status[item_type], item_type)
    def command(controller, key, status, comment):
        controller.update(item_type, dict(key=key, status=status, comment=comment))


create_update_command('asset')
create_update_command('risk')
