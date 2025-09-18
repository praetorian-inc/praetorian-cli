import click

import praetorian_cli.handlers.add
import praetorian_cli.handlers.aegis
import praetorian_cli.handlers.agent
import praetorian_cli.handlers.delete
import praetorian_cli.handlers.enrich
import praetorian_cli.handlers.get
import praetorian_cli.handlers.imports
import praetorian_cli.handlers.link
import praetorian_cli.handlers.list
import praetorian_cli.handlers.script
import praetorian_cli.handlers.search
import praetorian_cli.handlers.test
import praetorian_cli.handlers.unlink
import praetorian_cli.handlers.update
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.configure import configure
from praetorian_cli.sdk.keychain import Keychain


@click.group()
@click.option('--profile', default='United States', help='The profile to use in the keychain file', show_default=True)
@click.option('--account', default=None, help='Assume role into this account')
@click.option('--debug', is_flag=True, default=False, help='Run the CLI in debug mode')
@click.option('--proxy', default='', help='The proxy to use in the CLI')
@click.pass_context
@click.version_option()
def main(click_context, profile, account, debug, proxy):
    if debug:
        click.echo('Running in debug mode.')
    chariot.is_debug = debug
    click_context.obj = {'keychain': Keychain(profile, account), 'proxy': proxy}
    praetorian_cli.handlers.script.load_dynamic_commands()


main.add_command(chariot)
main.add_command(configure)
