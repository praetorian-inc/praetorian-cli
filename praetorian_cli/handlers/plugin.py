import os
from inspect import signature
from os import environ, listdir
from os.path import join

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.cli_decorators import load_raw_script
from praetorian_cli.plugins.commands import example, nessus_api, nessus_xml


@chariot.group()
@cli_handler
def plugin(controller):
    """ Run a plugin command """
    pass


@plugin.command('example')
@cli_handler
@click.argument('arg', required=False)
@click.option('--opt', required=False, help='A string option')
def example_command(sdk, arg, opt):
    """ An example static plugin command (packaged with the CLI)

        ARG is a string argument
    """
    example.run(sdk, arg, opt)


@plugin.command('nessus-api')
@cli_handler
@click.option('--url', required=True, help='URL of the Nessus server',
              prompt='What is the URL of the Nessus server?')
@click.option('--api-key', required=True, help='Nessus API key',
              prompt='What is the API key?')
@click.option('--secret-key', required=True, help='Nessus secret key',
              prompt='What is the secret key?', hide_input=True)
def nessue_api_command(controller, url, api_key, secret_key):
    """ Import Nessus results via API """
    nessus_api.report_vulns(controller, url, api_key, secret_key)


@plugin.command('nessus-xml')
@cli_handler
@click.option('--file', required=True, help='Path to the Nessus XML export file (.nessus)',
              prompt='What is the path to the Nessus XML export file (.nessus)?')
def nessus_xml_command(controller, file):
    """ Import Nessus results via XML export file (.nessus) """
    nessus_xml.report_vulns(controller, file)


def load_dynamic_commands():
    """ If the PRAETORIAN_SCRIPTS_PATH env variable is defined,
        load all the plugin commands defined there in those paths. """
    if 'PRAETORIAN_SCRIPTS_PATH' in environ:
        for directory in environ['PRAETORIAN_SCRIPTS_PATH'].split(os.pathsep):
            load_directory(directory)


def load_directory(path):
    """ Scan all the Python files in the directory for plugin commands.
        Files with a register() function will get called to add a command. """
    for file in listdir(path):
        if file.endswith('.py'):
            try:
                plugin_module = load_raw_script(join(path, file))
            except Exception as err:
                # This catches any compilation or execution errors of the py files that happen
                # to be in the directory.
                pass
            else:
                if (hasattr(plugin_module, 'register') and callable(plugin_module.register)
                        and len(signature(plugin_module.__dict__['register']).parameters) == 1):
                    plugin_module.register(plugin)


load_dynamic_commands()
