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
@click.argument('arg1', type=str, required=True, help="arg1 of hello command")
@click.argument('arg2', type=int, required=True, help="arg2 of hello command")
@click.option('--opt1', default=None, help="opt1 option of hello command")
@click.option('--sow', required=True,  help="sow option of hello command; will prompt if not supplied",
              prompt='What is the SOW number?')
def hello_command(ctx: click.Context, arg1: str, arg2: int, opt1, sow):
    """ This is a simple hello command echoing the arguments """
    click.echo(f'Hello World!')
    click.echo(f'arg1 = {arg1}')
    click.echo(f'arg2 = {arg2}')
    click.echo(f'opt1 = {opt1}')
    click.echo(f'sow = {sow}')


def register(chariot: click.MultiCommand):
    chariot.add_command(hello_command)
