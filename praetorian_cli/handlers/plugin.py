import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts import hello_plugin


@chariot.group()
@cli_handler
def plugin(controller):
    """Run a plugin with arguments"""
    pass


@plugin.command('hello')
@click.argument('args', nargs=-1)
@cli_handler
def hello(controller, args):
    """Run the hello plugin"""
    hello_plugin.hello_function(controller, args)
