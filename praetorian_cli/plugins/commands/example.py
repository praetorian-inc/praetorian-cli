"""
This script runs as a plugin command to the Praetorian CLI.

Example usage:
    praetorian chariot plugin example abc 123 --sow 2024-06-0001 --flag-opt --opt1 xyz
"""
import json

import click


def run(sdk, arg, opt):
    """ Print the arguments and options provided to the hello command
        and call the SDK to demonstrate that this function scope has
        full access to the Chariot SDK.
     """

    # demonstrate access to the command line arguments and options
    click.echo(f'Hello World! This is an example of a static plugin command extending the core CLI functionality\n')
    click.echo(f'arg = {arg}')
    click.echo(f'opt = {opt}')

    # demonstrate authenticated access to the Chariot SDK
    assets_response = sdk.my(dict(key='#asset#'))
    click.echo('Listing of assets:\n')
    click.echo(json.dumps(assets_response, indent=4))

    click.echo('\nExiting the example command.')
