import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.scripts import hello_command, nessus_run


@chariot.group()
@cli_handler
def run(controller):
    """Run a script with arguments"""
    pass


@run.command('hello')
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


@run.command('nessus')
@cli_handler
@click.argument('args', nargs=-1)
@click.option('--url', required=True, help='URL of the Nessus server',
              prompt='What is the URL of the Nessus server?')
@click.option('--api-key', required=True, help='Nessus API key',
              prompt='What is the API key?')
@click.option('--secret-key', required=True, help='Nessus secret key',
              prompt='What is the secret key?')
def nessus(controller, url, api_key, secret_key):
    """ Run a Nessus scan """
    nessus_run.report_vulns(controller, url, api_key, secret_key)
