import click


@click.group()
@click.pass_context
def chariot(click_context):
    # import done here to avoid circular import errors in praetorian_cli/handlers/cli_decorators.py
    from praetorian_cli.sdk.chariot import Chariot

    """ Command group for interacting with the Chariot product """
    # Replace the click context (previously a Keychain instance) with a Chariot
    # instance, after creating it using the Keychain instance.
    keychain = click_context.obj
    chariot = Chariot(keychain=keychain)
    click_context.obj = chariot
