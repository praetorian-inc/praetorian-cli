from importlib.util import find_spec
from os.path import join, dirname
from os import environ, listdir

import click

from praetorian_cli.handlers.cli_decorators import load_raw_script
from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(ctx):
    """ Chariot API access in the new and different file """
    ctx.obj = Chariot(keychain=ctx.obj)

@chariot.group()
@click.pass_context
def plugin(ctx):
    """ Plugin commands """
    pass


def load_plugin_commands():
    load_directory(join(dirname(find_spec('praetorian_cli').origin), 'scripts'))
    if 'PRAETORIAN_SCRIPTS_PATH' in environ:
        load_directory(environ['PRAETORIAN_SCRIPT_PATH'])


def load_directory(path):
    for file in listdir(path):
        if file.endswith('.py'):
            plugin = load_raw_script(join(path, file))
            if hasattr(plugin, 'register') and callable(plugin.register):
                plugin.register(chariot)


load_plugin_commands()
