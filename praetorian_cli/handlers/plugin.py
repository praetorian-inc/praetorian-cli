import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts import hello_command


@chariot.group()
@cli_handler
def plugin(controller):
    """ Run a plugin command """
    pass


@plugin.command('hello')
@cli_handler
@click.argument('arg1', type=str)
@click.argument('arg2', type=int)
@click.option('--opt1', default=None, help='A string option')
@click.option('--sow', required=True,
              help='A mandatory option to provide the SOW number; will prompt if not supplied',
              prompt='SOW number is required. What is the SOW number?')
@click.option('--flag-opt', is_flag=True, help='A flag option')
def hello(controller, arg1, arg2, opt1, sow, flag_opt):
    """ Example plugin command, extending the core list of commands """
    hello_command.hello_function(controller, arg1, arg2, opt1, sow, flag_opt)
