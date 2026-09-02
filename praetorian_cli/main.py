import truststore

# Configure TLS before importing HTTP clients so they use the OS trust store.
truststore.inject_into_ssl()

import click
from click.core import ParameterSource

import praetorian_cli.handlers.access
import praetorian_cli.handlers.add
import praetorian_cli.handlers.aegis
import praetorian_cli.handlers.agent
import praetorian_cli.handlers.critfinder
import praetorian_cli.handlers.delete
import praetorian_cli.handlers.enrich
import praetorian_cli.handlers.engagement
import praetorian_cli.handlers.find
import praetorian_cli.handlers.export
import praetorian_cli.handlers.get
import praetorian_cli.handlers.hunt
import praetorian_cli.handlers.run
import praetorian_cli.handlers.imports
import praetorian_cli.handlers.link
import praetorian_cli.handlers.list
import praetorian_cli.handlers.query
import praetorian_cli.handlers.report
import praetorian_cli.handlers.script
import praetorian_cli.handlers.search
import praetorian_cli.handlers.test
import praetorian_cli.handlers.unlink
import praetorian_cli.handlers.update
import praetorian_cli.handlers.vm
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.configure import configure
from praetorian_cli.sdk.keychain import Keychain


class InvocationPathGroup(click.Group):
    """Record the Click-resolved public command path before root setup runs."""

    def resolve_command(self, ctx, args):
        command_name, command, remaining = super().resolve_command(ctx, args)
        nested_name = remaining[0] if remaining else None
        ctx.meta["praetorian_invocation_path"] = (command_name, nested_name)
        return command_name, command, remaining


def _is_test_invocation(click_context):
    path = click_context.meta.get("praetorian_invocation_path", ())
    return click_context.invoked_subcommand == "test" or path == ("chariot", "test")


# A test target may only be built from values the user actually supplied. Anything
# else -- notably the declared --profile default -- must reach the explicit-target
# check as a value it rejects, so a destructive suite can never run against a
# default the user never chose.
SUPPLIED_PARAMETER_SOURCES = (ParameterSource.COMMANDLINE, ParameterSource.ENVIRONMENT)


def _supplied(click_context, name, value):
    if click_context.get_parameter_source(name) in SUPPLIED_PARAMETER_SOURCES:
        return value
    return None


def _test_target(click_context, profile, account, proxy):
    return praetorian_cli.handlers.test.TestTarget(
        profile=_supplied(click_context, 'profile', profile),
        account=_supplied(click_context, 'account', account),
        proxy=proxy,
    )


@click.group(cls=InvocationPathGroup)
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
    if _is_test_invocation(click_context):
        click_context.obj = _test_target(click_context, profile, account, proxy)
        return
    click_context.obj = {'keychain': Keychain(profile, account), 'proxy': proxy}
    praetorian_cli.handlers.script.load_dynamic_commands()


main.add_command(chariot)
main.add_command(configure)


@click.group()
@click.option('--profile', default='United States', help='The profile to use in the keychain file', show_default=True)
@click.option('--account', default=None, help='Assume role into this account')
@click.option('--debug', is_flag=True, default=False, help='Run the CLI in debug mode')
@click.option('--proxy', default='', help='The proxy to use in the CLI')
@click.pass_context
@click.version_option()
def guard_main(click_context, profile, account, debug, proxy):
    """Guard CLI - Praetorian's offensive security platform."""
    if debug:
        click.echo('Running in debug mode.')
    chariot.is_debug = debug

    if _is_test_invocation(click_context):
        click_context.obj = _test_target(click_context, profile, account, proxy)
        return

    from praetorian_cli.sdk.chariot import Chariot
    click_context.obj = Chariot(Keychain(profile, account), proxy=proxy)
    praetorian_cli.handlers.script.load_dynamic_commands()


# Add all chariot commands to guard_main
for cmd_name, cmd in chariot.commands.items():
    guard_main.add_command(cmd, cmd_name)
guard_main.add_command(configure)
