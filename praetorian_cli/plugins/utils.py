from importlib import import_module
from shutil import which
from functools import wraps

from click import echo
from semver import compare


def requires_command(command, help=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if which(command) is not None:
                return func(*args, **kwargs)
            if help:
                exit_with_message(help)
            else:
                exit_with_message(f'This plugin requires the {command} command. Please install it.')

        return wrapper

    return decorator


def requires_package(package, version=None, help=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            def not_satisfied():
                if help:
                    exit_with_message(help)
                else:
                    if version:
                        exit_with_message(
                            f'This plugin requires the {package} ({version}) package. Please install it with pip.')
                    else:
                        exit_with_message(
                            f'This plugin requires the {package} package. Please install it with pip.')

            try:
                module = import_module(package)
            except:
                not_satisfied()

            if version and compare(module.__version__, version) == -1:
                not_satisfied()

            return func(*args, **kwargs)

        return wrapper

    return decorator



def exit_with_message(message):
    echo(message, err=True)
    exit(1)
