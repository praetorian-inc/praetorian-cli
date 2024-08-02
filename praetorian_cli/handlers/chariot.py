import click

from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(ctx):
    """ Command group for interacting with the Chariot product """
    ctx.obj = Chariot(keychain=ctx.obj)
