import click

""" 
For developers: 
You can use this as a template for testing new commands/scripts.
It is hidden from the help menu, but can still be called from the command line. 
Usage : 
    praetorian chariot hello <name>
"""


@click.command(hidden=True)
@click.pass_context
@click.argument('name', type=str, required=True)
def hello(ctx: click.Context, name: str):
    """ This is a simple hello command """
    click.echo(f'Hello {name}')


def register(chariot: click.MultiCommand):
    chariot.add_command(hello)
