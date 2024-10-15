import sys
from inspect import signature
from os import environ, listdir, pathsep
from os.path import join
from types import ModuleType

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.utils import error


@chariot.group()
def script():
    """ Run a script """
    pass


def load_dynamic_commands():
    """ If the PRAETORIAN_SCRIPTS_PATH env variable is defined,
        load all the script defined there in those paths. """
    if 'PRAETORIAN_SCRIPTS_PATH' in environ:
        for directory in environ['PRAETORIAN_SCRIPTS_PATH'].split(pathsep):
            load_directory(directory)


def load_directory(path):
    """ Scan all the Python files in the directory for scripts that are
        compatible with the CLI. Files with a register() function will
        get called to add a command under the 'script' group. """
    try:
        for file in listdir(path):
            if file.endswith('.py'):
                try:
                    cli_script = load_script(join(path, file))
                except Exception as err:
                    # This catches any compilation or execution error of the Python files that happen
                    # to be in the directory. And skip them unless --debug is set.
                    if chariot.is_debug:
                        click.echo(f'Error loading {file} in {path}:')
                        raise err
                    pass
                else:
                    if (hasattr(cli_script, 'register') and callable(cli_script.register)
                            and len(signature(cli_script.__dict__['register']).parameters) == 1):
                        cli_script.register(script)
    except FileNotFoundError as err:
        error(f'Directory {path} does not exist.')


def load_script(path):
    module = ModuleType('cli-script')
    module.__file__ = path
    with open(path, 'r') as code_file:
        exec(compile(code_file.read(), path, 'exec'), module.__dict__)
    sys.modules['cli-script'] = module
    return module
