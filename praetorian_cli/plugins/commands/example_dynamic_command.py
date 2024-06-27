"""
For developers:
You can use this as a template for testing new plugin commands.

Usage:
    praetorian chariot plugin dynamic-command <YOUR_NAME>

"""

import click
from praetorian_cli.handlers.cli_decorators import cli_handler


@click.command('dynamic-command')
@cli_handler
@click.argument('name', type=str, required=True)
def dynamic_command(controller, name):
    """ An example of a dynamic plugin command. It can utilize Click decorators.
        This function is the entry point for executing the command. """
    click.echo(f'Hello {name}')


def register(plugin_group: click.MultiCommand):
    """ This function has to be defined for this file to be dynamically loaded
        to the CLI as a command. This function has a single argument that is a
        Click command group. It is called by the load_directory function in
        praetorian_cli.handlers.plugin """
    plugin_group.add_command(dynamic_command)
