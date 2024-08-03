import os
import sys
from inspect import signature
from os import environ, listdir
from os.path import join
from types import ModuleType

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts.commands import nessus_api, nessus_xml


@chariot.group('script')
@cli_handler
def script(controller):
    """ Run a script """
    pass


@script.command('nessus-api')
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


@script.command('nessus-xml')
@cli_handler
@click.option('--file', required=True, help='Path to the Nessus XML export file (.nessus)',
              prompt='What is the path to the Nessus XML export file (.nessus)?')
def nessus_xml_command(controller, file):
    """ Import Nessus results via XML export file (.nessus) """
    nessus_xml.report_vulns(controller, file)


def load_dynamic_commands(debug=False):
    """ If the PRAETORIAN_SCRIPTS_PATH env variable is defined,
        load all the script defined there in those paths. """
    if 'PRAETORIAN_SCRIPTS_PATH' in environ:
        for directory in environ['PRAETORIAN_SCRIPTS_PATH'].split(os.pathsep):
            load_directory(directory, debug)


def load_directory(path, debug=False):
    """ Scan all the Python files in the directory for scripts that are
        compatible with the CLI. Files with a register() function will
        get called to add a command under the 'script' group. """
    try:
        for file in listdir(path):
            if file.endswith('.py'):
                try:
                    cli_script = load_script(join(path, file))
                except Exception as err:
                    # This catches any compilation or execution error of the Python files that happen
                    # to be in the directory. And skip them unless --debug is set.
                    if debug:
                        click.echo(f'Error loading {file} in {path}:')
                        raise err
                    pass
                else:
                    if (hasattr(cli_script, 'register') and callable(cli_script.register)
                            and len(signature(cli_script.__dict__['register']).parameters) == 1):
                        cli_script.register(script)
    except FileNotFoundError as err:
        click.echo(f'Directory {path} does not exist.', err=True)
        exit(1)


def load_script(path):
    module = ModuleType('cli-script')
    module.__file__ = path
    with open(path, 'r') as code_file:
        exec(compile(code_file.read(), path, 'exec'), module.__dict__)
    sys.modules['cli-script'] = module
    return module
