"""
For developers:
You can use this as a template for testing new plugin commands.

Usage:
    praetorian chariot plugin dynamic-command <YOUR_NAME>

"""

import click

from praetorian_cli.handlers.cli_decorators import cli_handler


# The dynamic_command() function is the entry point for the command.
# In this example, it has a single argument on the command line, ie, name.
# The first argument, controller, is the instance object of
# praetorian_cli.sdk.Chariot. It give you authenticated access to all
# API functions in the Chariot class, such as my(), add(), etc.
#
# Furthermore, you can utilize Click decorators to define user-friendly
# command line arguments and options.
@click.command('dynamic-command')
@cli_handler
@click.argument('name', type=str, required=True)
def dynamic_command(controller, name):
    """ An example of a dynamic plugin command """
    click.echo(f'Hello {name}')


def register(plugin_group: click.MultiCommand):
    """ This function has to be defined for this file to be dynamically loaded
        to the CLI as a command. This function has a single argument that is a
        Click command group. It is called by the load_directory function in
        praetorian_cli.handlers.plugin. Once registered, this command shows up
        in the 'plugin' group """
    plugin_group.add_command(dynamic_command)
