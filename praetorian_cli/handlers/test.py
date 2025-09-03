import os
import sys
import subprocess

import click
import pytest

import praetorian_cli.sdk.test as test_module
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.command()
@cli_handler
@click.option('-s', '--suite', type=click.Choice(['coherence', 'cli', 'tui']), help='Run a specific test suite')
@click.argument('key', required=False)
def test(chariot, key, suite):
    """ Run integration test suite """
    os.environ['CHARIOT_TEST_PROFILE'] = chariot.keychain.profile
    os.environ['CHARIOT_PROXY'] = chariot.proxy
    command = [test_module.__path__[0]]
    if key:
        command.extend(['-k', key])
    if suite:
        command.extend(['-m', suite])
    # Run pytest in a subprocess to isolate from CLI pre-imports
    args = [sys.executable, '-m', 'pytest'] + command
    result = subprocess.run(args)
    raise SystemExit(result.returncode)
