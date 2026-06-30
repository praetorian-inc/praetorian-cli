from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group('enrichment')
def enrichment():
    """Manage enrichment plugins — enable/disable data enrichment sources, manage API keys and credits.

    \b
    Enrichment plugins augment Guard findings with external data sources (e.g.
    Shodan, VirusTotal). This command group covers the admin side: listing
    available plugins, toggling them on or off (individually or globally),
    inspecting and setting per-plugin credits, and managing the master API key
    that a plugin uses to call its upstream service.

    \b
    Common workflows:
        - guard enrichment list
        - guard enrichment enable shodan
        - guard enrichment set-credits shodan --amount 500
        - guard enrichment key set shodan --key sk-abc123
    """
    pass


# ---------------------------------------------------------------------------
# Plugin listing / inspection
# ---------------------------------------------------------------------------

@enrichment.command('list')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def list_enrichments(sdk, json_output):
    """List all enrichment plugins with their enabled state and credits.

    \b
    Example usages:
        - guard enrichment list
        - guard enrichment list --json-output
    """
    data = sdk.get('enrichment')

    if json_output:
        print_json(data)
        return

    plugins = data if isinstance(data, list) else data.get('plugins', data.get('data', []))
    if not plugins:
        click.echo('No enrichment plugins found.')
        return

    name_w = max((len(str(p.get('name', p.get('plugin', '')))) for p in plugins), default=20)
    header = f"{'PLUGIN':<{name_w}}  {'ENABLED':<8}  {'CREDITS':>10}"
    click.echo(header)
    click.echo('-' * len(header))

    for plugin in plugins:
        name = str(plugin.get('name', plugin.get('plugin', 'unknown')))
        enabled = plugin.get('enabled', False)
        credits_val = plugin.get('credits', plugin.get('remaining_credits', 'N/A'))

        enabled_str = click.style('yes', fg='green') if enabled else click.style('no', fg='red')
        click.echo(f"{name:<{name_w}}  {enabled_str:<8}  {str(credits_val):>10}")


@enrichment.command('show')
@cli_handler
@click.argument('plugin')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def show_enrichment(sdk, plugin, json_output):
    """Show details for a specific enrichment PLUGIN.

    \b
    Example usages:
        - guard enrichment show shodan
        - guard enrichment show virustotal --json-output
    """
    data = sdk.get(f'enrichment/{quote(plugin, safe="")}')

    if json_output:
        print_json(data)
        return

    click.echo(f"Plugin:  {plugin}")
    enabled = data.get('enabled', False)
    enabled_str = click.style('yes', fg='green') if enabled else click.style('no', fg='red')
    click.echo(f"Enabled: {enabled_str}")
    credits_val = data.get('credits', data.get('remaining_credits', 'N/A'))
    click.echo(f"Credits: {credits_val}")
    for key, val in data.items():
        if key not in ('enabled', 'credits', 'remaining_credits', 'name', 'plugin'):
            click.echo(f"{key}: {val}")


# ---------------------------------------------------------------------------
# Enable / disable individual plugin
# ---------------------------------------------------------------------------

@enrichment.command('enable')
@cli_handler
@click.argument('plugin')
def enable_enrichment(sdk, plugin):
    """Enable a specific enrichment PLUGIN.

    \b
    Example usages:
        - guard enrichment enable shodan
        - guard enrichment enable virustotal
    """
    result = sdk.put(f'enrichment/{quote(plugin, safe="")}/enabled', {'enabled': True})
    click.echo(click.style('Enabled: ', fg='green') + plugin)
    print_json(result)


@enrichment.command('disable')
@cli_handler
@click.argument('plugin')
def disable_enrichment(sdk, plugin):
    """Disable a specific enrichment PLUGIN.

    \b
    Example usages:
        - guard enrichment disable shodan
        - guard enrichment disable virustotal
    """
    result = sdk.put(f'enrichment/{quote(plugin, safe="")}/enabled', {'enabled': False})
    click.echo(click.style('Disabled: ', fg='red') + plugin)
    print_json(result)


# ---------------------------------------------------------------------------
# Global enable / disable
# ---------------------------------------------------------------------------

@enrichment.command('global-enable')
@cli_handler
def global_enable(sdk):
    """Turn on global enrichment (enables the enrichment subsystem as a whole).

    \b
    Example usages:
        - guard enrichment global-enable
    """
    result = sdk.put('enrichment/global/enabled', {'enabled': True})
    click.echo(click.style('Global enrichment enabled.', fg='green'))
    print_json(result)


@enrichment.command('global-disable')
@cli_handler
def global_disable(sdk):
    """Turn off global enrichment (suspends all enrichment regardless of plugin state).

    \b
    Example usages:
        - guard enrichment global-disable
    """
    result = sdk.put('enrichment/global/enabled', {'enabled': False})
    click.echo(click.style('Global enrichment disabled.', fg='red'))
    print_json(result)


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------

@enrichment.command('credits')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def list_credits(sdk, json_output):
    """Show credit balances for all enrichment plugins.

    \b
    Example usages:
        - guard enrichment credits
        - guard enrichment credits --json-output
    """
    data = sdk.get('enrichment/credits')

    if json_output:
        print_json(data)
        return

    plugins = data if isinstance(data, list) else data.get('plugins', data.get('data', []))
    if not plugins:
        click.echo('No credit data found.')
        return

    name_w = max((len(str(p.get('name', p.get('plugin', '')))) for p in plugins), default=20)
    header = f"{'PLUGIN':<{name_w}}  {'CREDITS':>10}"
    click.echo(header)
    click.echo('-' * len(header))

    for plugin in plugins:
        name = str(plugin.get('name', plugin.get('plugin', 'unknown')))
        credits_val = plugin.get('credits', plugin.get('remaining_credits', 'N/A'))
        click.echo(f"{name:<{name_w}}  {str(credits_val):>10}")


@enrichment.command('plugin-credits')
@cli_handler
@click.argument('plugin')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def plugin_credits(sdk, plugin, json_output):
    """Show the credit balance for a specific enrichment PLUGIN.

    \b
    Example usages:
        - guard enrichment plugin-credits shodan
        - guard enrichment plugin-credits virustotal --json-output
    """
    data = sdk.get(f'enrichment/{quote(plugin, safe="")}/credits')

    if json_output:
        print_json(data)
        return

    credits_val = data.get('credits', data.get('remaining_credits', data))
    click.echo(f"{plugin}: {credits_val} credits")


@enrichment.command('set-credits')
@cli_handler
@click.argument('plugin')
@click.option('--amount', required=True, type=int, help='Number of credits to assign to the plugin')
def set_credits(sdk, plugin, amount):
    """Set the credit limit for a specific enrichment PLUGIN.

    \b
    Example usages:
        - guard enrichment set-credits shodan --amount 500
        - guard enrichment set-credits virustotal --amount 1000
    """
    if amount < 0:
        error('--amount must be a non-negative integer')

    result = sdk.put(f'enrichment/{quote(plugin, safe="")}/credits', {'credits': amount})
    click.echo(f"Set credits for {click.style(plugin, bold=True)} to {click.style(str(amount), fg='cyan')}.")
    print_json(result)


# ---------------------------------------------------------------------------
# API key management (nested 'key' group)
# ---------------------------------------------------------------------------

@enrichment.group('key')
def key():
    """Manage the master API key for an enrichment plugin.

    \b
    Each enrichment plugin may use a master API key to call its upstream
    service. These subcommands let you view, update, or remove that key.
    """
    pass


@key.command('show')
@cli_handler
@click.argument('plugin')
def key_show(sdk, plugin):
    """Show the master API key configured for PLUGIN.

    \b
    Example usages:
        - guard enrichment key show shodan
    """
    data = sdk.get(f'enrichment/{quote(plugin, safe="")}/key')
    api_key = data.get('key', data.get('api_key'))
    if api_key and len(api_key) > 8:
        masked = '****' + api_key[-4:]
    elif api_key:
        masked = '(configured)'
    else:
        masked = None
    if masked:
        click.echo(f"API key for {plugin}: {masked}")
    else:
        click.echo(f"No API key configured for {plugin}.")


@key.command('set')
@cli_handler
@click.argument('plugin')
@click.option('--key', 'api_key', required=True, help='The API key to store for this plugin')
def key_set(sdk, plugin, api_key):
    """Set (or replace) the master API key for PLUGIN.

    \b
    Example usages:
        - guard enrichment key set shodan --key sk-abc123
        - guard enrichment key set virustotal --key vt-xyz789
    """
    result = sdk.put(f'enrichment/{quote(plugin, safe="")}/key', {'key': api_key})
    click.echo(click.style('API key updated for ', fg='green') + plugin + '.')
    print_json(result)


@key.command('delete')
@cli_handler
@click.argument('plugin')
def key_delete(sdk, plugin):
    """Delete the master API key for PLUGIN.

    \b
    Example usages:
        - guard enrichment key delete shodan
    """
    result = sdk.delete(f'enrichment/{quote(plugin, safe="")}/key', {}, {})
    click.echo(click.style('API key removed for ', fg='red') + plugin + '.')
    print_json(result)
