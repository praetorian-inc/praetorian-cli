import sys

import click


def prompt_account_selection(sdk):
    """Prompt the user to select an account if none was explicitly provided.

    Temporarily clears the keychain account so the API call lists accounts
    from the login principal's perspective. Restores the original account
    on failure or if no accounts are available.
    """
    keychain = sdk.keychain
    keychain.load()
    saved_account = keychain.account
    keychain.account = None
    try:
        accounts_data, _ = sdk.accounts.list()
        account_names = sorted(set(a['name'] for a in accounts_data))
        if account_names:
            click.echo('Available accounts:')
            for i, acct in enumerate(account_names, 1):
                click.echo(f'  {i}. {acct}')
            raw = click.prompt('Select account (or "exit" to quit)')
            if raw.strip().lower() == 'exit':
                raise SystemExit(0)
            try:
                choice = int(raw)
            except ValueError:
                click.echo(f'Error: invalid input: {raw}')
                raise SystemExit(1)
            if choice < 1 or choice > len(account_names):
                click.echo(f'Error: must be between 1 and {len(account_names)}')
                raise SystemExit(1)
            sdk.accounts.assume_role(account_names[choice - 1])
        else:
            keychain.account = saved_account
    except (KeyboardInterrupt, click.Abort, SystemExit):
        raise SystemExit(0)
    except Exception:
        keychain.account = saved_account


@click.group()
@click.pass_context
def chariot(click_context):
    # import done here to avoid circular import errors in praetorian_cli/handlers/cli_decorators.py
    from praetorian_cli.sdk.chariot import Chariot

    """ Command group for interacting with the Guard product """
    # Replace the click context (previously a Keychain instance) with a Chariot
    # instance, after creating it using the Keychain instance.
    keychain = click_context.obj['keychain']
    proxy = click_context.obj['proxy']

    chariot = Chariot(keychain=keychain, proxy=proxy)

    if not click_context.obj.get('explicit_account') and sys.stdin.isatty():
        prompt_account_selection(chariot)

    click_context.obj = chariot
