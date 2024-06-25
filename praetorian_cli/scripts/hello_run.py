"""
This script runs as a plugin to the Praetorian CLI.
Example usage:
    praetorian chariot plugin hello
"""


def hello_function(controller, args, kwargs, strings):
    """Run the hello plugin"""
    print('Hello from the hello plugin!')
    print(f'Arguments: {args}')
    print(f'Keyword arguments: {kwargs}')
    print(f'Strings: {strings}')
