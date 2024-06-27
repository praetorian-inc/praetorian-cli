from shutil import which
from sys import stderr
from functools import wraps


def requires(command, help=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if which(command) is not None:
                return func(*args, **kwargs)
            if help:
                print(help, file=stderr)
            else:
                print(f"This function requires {command} to be installed.", file=stderr)
            exit(1)

        return wrapper

    return decorator
