import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
import praetorian_cli.sdk.test as test_module


@chariot.command('test')
@cli_handler
@click.option('-suite', '--suite', type=click.Choice(["coherence"]), help="Run a specific test suite")
@click.argument('key', required=False)
def trigger_all_tests(controller, key, suite):
    """ Run integration test suite """
    try:
        import pytest
    except ModuleNotFoundError:
        click.echo("Install pytest using 'pip install pytest' to run this command", err=True)
        return

    os.environ['CHARIOT_PROFILE'] = controller.keychain.profile
    command = [test_module.__path__[0]]
    if key:
        command.extend(['-k', key])
    if suite:
        command.extend(['-m', suite])
    pytest.main(command)
