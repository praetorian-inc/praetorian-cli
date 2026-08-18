import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group('enrichment')
def enrichment_group():
    """ Enrichment plugin administration """
    pass


@enrichment_group.command('status')
@cli_handler
def enrichment_status(sdk):
    """ Get global enrichment status

    \b
    Example usages:
        guard enrichment status
    """
    print_json(sdk.enrichment_admin.status())


@enrichment_group.command('enabled')
@cli_handler
def enrichment_enabled(sdk):
    """ Get bulk enabled state for all enrichment plugins

    \b
    Example usages:
        guard enrichment enabled
    """
    print_json(sdk.enrichment_admin.enabled())


@enrichment_group.command('global-enabled')
@cli_handler
def enrichment_global_enabled(sdk):
    """ Get global enrichment enabled state

    \b
    Example usages:
        guard enrichment global-enabled
    """
    print_json(sdk.enrichment_admin.global_enabled())


@enrichment_group.command('set-global-enabled')
@cli_handler
@click.option('--enabled/--disabled', required=True, help='Enable or disable global enrichment')
def set_global_enabled(sdk, enabled):
    """ Enable or disable global enrichment

    \b
    Example usages:
        guard enrichment set-global-enabled --enabled
        guard enrichment set-global-enabled --disabled
    """
    print_json(sdk.enrichment_admin.set_global_enabled(enabled))


@enrichment_group.command('credits')
@cli_handler
def enrichment_credits(sdk):
    """ Get bulk credit information for all enrichment plugins

    \b
    Example usages:
        guard enrichment credits
    """
    print_json(sdk.enrichment_admin.credits())


@enrichment_group.command('plugin-status')
@cli_handler
@click.argument('plugin')
def plugin_status(sdk, plugin):
    """ Get status for a specific enrichment plugin

    \b
    Example usages:
        guard enrichment plugin-status shodan
    """
    print_json(sdk.enrichment_admin.plugin_status(plugin))


@enrichment_group.command('plugin-credits')
@cli_handler
@click.argument('plugin')
def plugin_credits(sdk, plugin):
    """ Get credit information for a specific enrichment plugin

    \b
    Example usages:
        guard enrichment plugin-credits shodan
    """
    print_json(sdk.enrichment_admin.plugin_credits(plugin))


@enrichment_group.command('set-enabled')
@cli_handler
@click.argument('plugin')
@click.option('--enabled/--disabled', required=True, help='Enable or disable the plugin')
def set_enabled(sdk, plugin, enabled):
    """ Enable or disable a specific enrichment plugin

    \b
    Example usages:
        guard enrichment set-enabled shodan --enabled
        guard enrichment set-enabled shodan --disabled
    """
    print_json(sdk.enrichment_admin.set_plugin_enabled(plugin, enabled))


@enrichment_group.command('set-key')
@cli_handler
@click.argument('plugin')
def set_key(sdk, plugin):
    """ Set the API key for an enrichment plugin

    \b
    Reads the key from stdin to avoid exposing secrets in process arguments.

    \b
    Example usages:
        echo "sk-abc123" | guard enrichment set-key shodan
        guard enrichment set-key shodan < keyfile.txt
    """
    key = sys.stdin.read().strip()
    if not key:
        raise click.UsageError('No key provided on stdin. Pipe your key: echo "KEY" | guard enrichment set-key PLUGIN')
    print_json(sdk.enrichment_admin.set_plugin_key(plugin, key))
