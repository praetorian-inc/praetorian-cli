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


def load_cli_scripts():
    module_dir = os.path.dirname(
        importlib.util.find_spec('praetorian_cli').origin)
    scripts_dir = os.path.join(module_dir, 'scripts')
    plugins = [load_raw_script(os.path.join(scripts_dir, filename))
               for filename in os.listdir(scripts_dir) if filename.endswith('.py')]
    for plugin in filter(lambda p: hasattr(p, 'register') and callable(p.register), plugins):
        plugin.register(chariot)


load_cli_scripts()
