import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts import hello_command


@chariot.group()
@cli_handler
def run(controller):
    """Run a script with arguments"""
    pass


@run.command('hello')
@click.argument('arg1', type=str)
@click.argument('arg2', type=int)
@click.option('--opt1', default=None, help="A string option")
@click.option('--sow', required=True,
              help="A mandatory option to provide the SOW number; will prompt if not supplied",
              prompt='SOW number is required. What is the SOW number?')
@click.option('--flag-opt', is_flag=True, help='A flag option')
@cli_handler
def hello(controller, arg1, arg2, opt1, sow, flag_opt):
    """Run the hello plugin"""
    hello_command.hello_function(controller, arg1, arg2, opt1, sow, flag_opt)
