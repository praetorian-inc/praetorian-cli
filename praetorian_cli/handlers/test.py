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
@click.option('--profile', help='Keychain profile name (defaults to current profile)')
@click.option('--username', default='', help='Praetorian username')
@click.option('--password', default='', help='Praetorian password')
@click.option('--api', default='', help='API endpoint URL')
@click.option('--client-id', default='', help='Client ID')
@click.option('--account', default='', help='Account to use')
@click.option('--keychain-filepath', help='Custom path to keychain file')
@click.option('--iterations', type=int, default=3, help='Number of iterations for each test')
@click.option('--test', type=click.Choice(['assets', 'search', 'risks', 'all']), default='all', 
              help='Test category to run (default: all)')
@click.option('--output', help='Save results to this JSON file')
def test_speed(chariot, profile, username, password, api, client_id, account, keychain_filepath, 
               iterations, test, output):
    """ Run performance monitoring / heavy use tests """
    if profile is None:
        profile = chariot.keychain.profile
    
    speed_test = APISpeedTest(
        username=username,
        password=password,
        profile=profile,
        api=api,
        client_id=client_id,
        account=account,
        keychain_filepath=keychain_filepath
    )
    
    if test == 'all':
        speed_test.run_all_tests(iterations=iterations)
    elif test == 'assets':
        speed_test.run_asset_tests(iterations=iterations)
    elif test == 'search':
        speed_test.run_search_tests(iterations=iterations)
    elif test == 'risks':
        speed_test.run_risk_tests(iterations=iterations)
    
    speed_test.print_results()
    
    if output:
        speed_test.save_results(output)
