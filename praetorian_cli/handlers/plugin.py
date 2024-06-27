import os
from os.path import join
from os import environ, listdir
from inspect import signature

import click

from praetorian_cli.handlers.cli_decorators import load_raw_script
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.plugins.commands import example, report


@chariot.group()
@cli_handler
def plugin(controller):
    """ Run a plugin command """
    pass


@plugin.command('example')
@cli_handler
@click.argument('arg1', type=str)
@click.argument('arg2', type=int)
@click.option('--opt1', default=None, help='A string option')
@click.option('--sow', required=True,
              help='A mandatory option to provide the SOW number; will prompt if not supplied',
              prompt='SOW number is required. What is the SOW number?')
@click.option('--flag-opt', is_flag=True, help='A flag option')
def example_command(controller, arg1, arg2, opt1, sow, flag_opt):
    """ An example plugin command, extending the CLI

        ARG1 is a string argument; ARG2 is an integer argument
    """
    example.run(controller, arg1, arg2, opt1, sow, flag_opt)


@plugin.command('report')
@cli_handler
@click.argument('env_file', type=click.Path(exists=False), default='.env')
def report_command(controller, env_file):
    """ Praetorian reporting workflow """
    report.run(controller, env_file)


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
