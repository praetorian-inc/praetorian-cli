import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts import hello_run


@chariot.group()
@cli_handler
def run(controller):
    """Run a script with arguments"""
    pass


@run.command('hello')
@click.argument('args', nargs=-1)
@click.option('--kwargs', '-k', multiple=True, type=(str, str), help="Key-value pairs for the plugin")
@click.option('--strings', '-s', multiple=True, help="Multiple strings")
@cli_handler
def hello(controller, args, kwargs, strings):
    """Run the hello plugin"""
    hello_run.hello_function(controller, args, kwargs, strings)
