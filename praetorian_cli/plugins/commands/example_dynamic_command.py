"""
For developers:
You can use this as a template for writing new dynamic plugin commands.

Usage:
    praetorian chariot plugin dynamic-example AN_ARGUMENT --opt AN_OPTION
"""

import json

import click

from praetorian_cli.handlers.cli_decorators import cli_handler


# The dynamic_command() function is the entry point for the command.
# In this example, it has an argument and an option on the command line.
# The first argument to this function, sdk, is the instance object of
# praetorian_cli.sdk.Chariot. It give you authenticated access to all
# API functions in the Chariot class, such as my(), add(), etc.
#
# Furthermore, you can utilize all Click decorators to define
# user-friendly command line arguments and options.
@click.command('dynamic-example')
@cli_handler
@click.argument('arg', required=False)
@click.option('--opt', required=False, help='A string option')
def dynamic_command(sdk, arg, opt):
    """ An example dynamic plugin command (linked at run time)

        ARG is a string argument
    """

    # demonstrate access to the command line arguments and options
    click.echo(f'Hello World! This is an example of a dynamic plugin command extending the core CLI functionality\n')
    click.echo('You have supplied the following argument and option:')
    click.echo(f'arg = {arg}')
    click.echo(f'opt = {opt}')

    # demonstrate authenticated access to the Chariot SDK
    assets_response = sdk.my(dict(key='#asset#'))
    click.echo('Listing of assets:\n')
    click.echo(json.dumps(assets_response, indent=4))

    click.echo('\nExiting the dynamic-example command.')


def register(plugin_group: click.MultiCommand):
    """ This function has to be defined for this file to be dynamically loaded
        to the CLI as a command. This function has a single argument that is a
        Click command group. It is called by the load_directory function in
        praetorian_cli.handlers.plugin. Once registered, this command shows up
        in the 'plugin' group """
    plugin_group.add_command(dynamic_command)
