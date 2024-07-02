import click

from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(ctx):
    """ Chariot API access in the new and different file """
    ctx.obj = Chariot(keychain=ctx.obj)
