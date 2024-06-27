import os
import click

import importlib.util
from praetorian_cli.handlers.cli_decorators import load_raw_script
from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(ctx):
    """ Chariot API access in the new and different file """
    ctx.obj = Chariot(keychain=ctx.obj)
