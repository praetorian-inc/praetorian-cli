import click

import praetorian_cli.handlers.add  # noqa
import praetorian_cli.handlers.delete  # noqa
import praetorian_cli.handlers.get  # noqa
import praetorian_cli.handlers.link  # noqa
import praetorian_cli.handlers.list  # noqa
import praetorian_cli.handlers.plugin  # noqa
import praetorian_cli.handlers.search  # noqa
import praetorian_cli.handlers.test  # noqa
import praetorian_cli.handlers.unlink  # noqa
import praetorian_cli.handlers.update  # noqa
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.sdk.keychain import Keychain


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
@click.option('--profile', default='United States', help='The keychain profile to use', show_default=True)
@click.option('--account', default=None, help='Run command as an account you belong to')
def cli(ctx, profile, account):
    ctx.obj = Keychain(profile=profile, account=account)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command('configure')
@click.pass_context
def configure(ctx):
    """ Configure the CLI """
    click.echo('Enter your Praetorian credentials to store in the keychain')
    ctx.obj.configure()


cli.add_command(chariot)

if __name__ == '__main__':
    cli()
