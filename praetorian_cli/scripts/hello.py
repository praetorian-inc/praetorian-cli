import click


@click.command()
@click.pass_context
@click.argument('name', type=str, required=True)
def hello(ctx: click.Context, name: str):
    """ This is a simple hello command """
    click.echo(f'Hello {name}')


def register(chariot: click.MultiCommand):
    chariot.add_command(hello)
