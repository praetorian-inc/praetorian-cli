from functools import wraps
from shutil import which

from praetorian_cli.handlers.utils import error


def requires(command, help=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if which(command) is not None:
                return func(*args, **kwargs)
            if help:
                error(help)
            else:
                error(f'This function requires "{command}" to be installed.')

        return wrapper

    return decorator
