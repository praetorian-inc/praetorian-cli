import click

from praetorian_cli.sdk.chariot import Chariot


@click.group()
@click.pass_context
def chariot(click_context):
    """ Command group for interacting with the Chariot product """
    # Replace the click context (previously a Keychain instance) with a Chariot
    # instance, after creating it using the Keychain instance.
    keychain = click_context.obj
    chariot = Chariot(keychain=keychain)
    click_context.obj = chariot
