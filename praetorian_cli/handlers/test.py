import os

import click
import pytest

import praetorian_cli.sdk.test as test_module
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.command()
@cli_handler
@click.option('-s', '--suite', type=click.Choice(['coherence', 'cli']), help='Run a specific test suite')
@click.argument('key', required=False)
def test(chariot, key, suite):
    """ Run integration test suite """
    os.environ['CHARIOT_TEST_PROFILE'] = chariot.keychain.profile
    command = [test_module.__path__[0]]
    if key:
        command.extend(['-k', key])
    if suite:
        command.extend(['-m', suite])
    pytest.main(command)
