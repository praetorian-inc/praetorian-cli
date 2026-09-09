import click


@click.group()
@click.pass_context
def chariot(click_context):
    from praetorian_cli.handlers.test import TestTarget

    if isinstance(click_context.obj, TestTarget):
        return

    # Deferred import: keeps the cost of importing the whole SDK off the
    # module-import path, so `guard --help` and unrelated commands do not pay
    # for it. ENG-6585 owns making this lazy loading systematic.
    from praetorian_cli.sdk.chariot import Chariot

    """ Command group for interacting with the Guard product """
    # Replace the click context (previously a Keychain instance) with a Chariot
    # instance, after creating it using the Keychain instance.
    keychain = click_context.obj['keychain']
    proxy = click_context.obj['proxy']

    chariot = Chariot(keychain=keychain, proxy=proxy)
    click_context.obj = chariot
