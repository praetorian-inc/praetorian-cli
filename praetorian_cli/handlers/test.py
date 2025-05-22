import os

import click
import pytest

import praetorian_cli.sdk.test as test_module
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.sdk.test.test_speed import APISpeedTest


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


@chariot.command()
@cli_handler
@click.option('--profile', help='Keychain profile name (defaults to test profile)')
@click.option('--account', default='', help='Account to use')
@click.option('--iterations', type=int, default=3, help='Number of iterations for each test')
@click.option('--test', type=click.Choice(['assets', 'search', 'risks', 'all']), default='all', 
              help='Test category to run (default: all)')
@click.option('--output', help='Save results to this JSON file')
def test_speed(chariot, profile, account, iterations, test, output):
    speed_test = APISpeedTest(
        profile=profile,
        account=account,
        iterations=iterations
    )
    speed_test.run_tests(test, output=output)
