import os
import click

from praetorian_cli.handlers.cli_decorators import load_raw_script
from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(ctx):
    """ Chariot API access in the new and different file """
    ctx.obj = Chariot(keychain=ctx.obj)


def load_cli_scripts():
    plugins = [load_raw_script(os.path.join('scripts/', filename))
               for filename in os.listdir('scripts/')+ os.listdir(os.path.expanduser('~/.praetorian/')) if filename.endswith('.py')]
    for plugin in filter(lambda p: hasattr(p, 'register') and callable(p.register), plugins):
        plugin.register(chariot)


load_cli_scripts()
