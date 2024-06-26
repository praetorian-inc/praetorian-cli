"""
This script runs as a plugin command to the Praetorian CLI.

Example usage:
    praetorian chariot run hello abc 123 --sow 2024-06-0001 --flag-opt --opt1 xyz
"""
import json

import click

def hello_function(controller, arg1, arg2, opt1, sow, flag_opt):
    """ Print the arguments and options provided to the hello command
        and call the SDK to demonstrate that this function scope has
        full access to the Chariot SDK.
     """
    click.echo(f'Hello World!')
    click.echo(f'arg1 = {arg1} (type: {type(arg1)})')
    click.echo(f'arg2 = {arg2} (type: {type(arg2)})')
    click.echo(f'opt1 = {opt1}')
    click.echo(f'sow = {sow}')
    click.echo(f'flag_opt = {flag_opt}')

    seeds_response = controller.my(dict(key='#seed#'))
    click.echo('Listing of seeds:')
    click.echo(json.dumps(seeds_response, indent=4))
    