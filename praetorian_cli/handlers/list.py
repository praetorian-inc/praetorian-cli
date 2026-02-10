import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import list_params, pagination, cli_handler, praetorian_only
from praetorian_cli.handlers.utils import render_offset, render_list_results, pagination_size, error, print_json


@chariot.group()
def list():
    """ Get a list of entities from Guard """
    pass


@list.command()
@list_params('DNS', has_type=True)
def assets(chariot, filter, model_type, details, offset, page):
    """ List assets

   	Retrieve and display a list of assets.

    \b
    Example usages:
        - guard list assets
        - guard list assets --filter api.example.com
        - guard list assets --details
        - guard list assets --page all
        - guard list assets --type repository
    """
    render_list_results(chariot.assets.list(filter, model_type, pagination_size(page)), details)


@list.command()
@list_params('DNS of the associated assets')
def risks(chariot, filter, details, offset, page):
    """ List risks

    Retrieve and display a list of risks.

    \b
    Example usages:
        - guard list risks
        - guard list risks --filter api.example.com
        - guard list risks --details
        - guard list risks --page all
    """
    render_list_results(chariot.risks.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('account email address')
def accounts(chariot, filter, details, offset, page):
    """ List accounts

	Retrieve and display a list of your collaborators, as well as the accounts that
	you are authorized to access.

    \b
    Example usages:
        - guard list accounts
        - guard list accounts --filter john@praetorian.com
        - guard list accounts --details
        - guard list accounts --page all
    """
    render_list_results(chariot.accounts.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('Aegis ID', has_filter=False)
def aegis(chariot, details, offset, page):
    """ List Aegis

    Retrieve and display a list of Aegis instances.

    \b
    Example usages:
        - guard list aegis
        - guard list aegis --details
        - guard list aegis --page all
    """
    render_list_results(chariot.aegis.list(offset, pagination_size(page)), details)


@list.command()
@list_params('integration name')
def integrations(chariot, filter, details, offset, page):
    """ List integrations

	Retrieve and display a list of integration connections.

    \b
    Example usages:
        - guard list integrations
        - guard list integrations --filter gcp
        - guard list integrations --details
        - guard list integrations --page all
    """
    render_list_results(chariot.integrations.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('DNS of the job asset')
def jobs(chariot, filter, details, offset, page):
    """
    List jobs

    Retrieve and display a list of recently scheduled jobs. You can use this
    to find out the status of the jobs, such as queued, running, passed, or failed.

    \b
    Example usages:
        - guard list jobs
        - guard list jobs --filter www.example.com
        - guard list jobs --details
        - guard list jobs --page all
    """
    render_list_results(chariot.jobs.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('file path')
def files(chariot, filter, details, offset, page):
    """ List files

    Retrieve and display a list of files in the Guard file system.

    \b
    Example usages:
        - guard list files
        - guard list files --filter "home/reports/cloud-assessment-2024-"
        - guard list files --details
        - guard list files --page all
     """
    render_list_results(chariot.files.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('definition name', has_details=False)
def definitions(chariot, filter, offset, page):
    """ List risk definitions

    Retrieve and display a list of risk definitions.

    \b
    Example usages:
        - guard list definitions
        - guard list definitions --filter "home/reports/cloud-assessment-2024-"
        - guard list definitions --page all
    """
    definitions, next_offset = chariot.definitions.list(filter, offset, pagination_size(page))
    click.echo('\n'.join(definitions))
    render_offset(next_offset)


@list.command()
@list_params('attribute name')
@click.option('-k', '--key', default=None, help='Filter by an asset or risk key')
def attributes(chariot, filter, key, details, offset, page):
    """ List attributes

    Retrieve and display a list of attributes.

    \b
    Filtering options:
        - Use the --filter option to filter on the name of the attribute.
        - Use the --key option to filter for attributes of an asset or a risk.
        - You can only filter using either of the above, not together.

    \b
    Example usages:
        - guard list attributes
        - guard list attributes --filter proto
        - guard list attributes --key "#risk#www.example.com#CVE-2024-23049"
        - guard list attributes --details
        - guard list attributes --page all
    """
    render_list_results(chariot.attributes.list(filter, key, offset, pagination_size(page)), details)


@list.command()
@list_params('DNS')
@click.option('-t', '--type', help='Filter by seed type (e.g., asset, addomain)')
def seeds(chariot, type, filter, details, offset, page):
    """ List seeds

   	Retrieve and display a list of seeds. Seeds are now assets with the 'Seed' label.

    \b
    Example usages:
        - guard list seeds
        - guard list seeds --type asset
        - guard list seeds --type addomain
        - guard list seeds --type asset --filter example.com
        - guard list seeds --details
        - guard list seeds --page all
    """
    # Note: filter restriction removed since we're using different key format now
    render_list_results(chariot.seeds.list(type, filter, pagination_size(page)), details)


@list.command()
@list_params('DNS')
def preseeds(chariot, filter, details, offset, page):
    """ List adjacent domain discovery patterns (pre-seeds)

   	Retrieve and display a list of pre-seeds.

    \b
    Example usages:
        - guard list preseeds
        - guard list preseeds --filter tlscert
        - guard list preseeds --details
        - guard list preseeds --page all
    """
    render_list_results(chariot.preseeds.list(filter, offset, pagination_size(page)), details)


@list.command
@click.option('-f', '--filter', default='', help='Filter by statistic type or name')
@click.option('--from', 'from_date', help='Start date (YYYY-MM-DD)')
@click.option('--to', 'to_date', help='End date (YYYY-MM-DD)')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@click.option('--help-stats', is_flag=True, help='Show detailed information about statistic types')
@pagination
@cli_handler
def statistics(chariot, filter, from_date, to_date, details, offset, page, help_stats):
    """ List statistics
    Retrieve and display a list of statistics with optional date range filtering.
    Use --help-stats for detailed information about available statistic types.

    \b
    Example usages:
        - guard list statistics
        - guard list statistics --filter "my#status"
        - guard list statistics --from 2024-12-01 --to 2024-12-31
        - guard list statistics --details
        - guard list statistics --page all
        - guard list statistics --help-stats
    """
    if help_stats:
        click.echo(chariot.statistics.util.get_statistics_help())
        return

    # Map common filter aliases to StatsFilter values
    filter_map = {
        'risks': chariot.statistics.util.RISKS,
        'risk_events': chariot.statistics.util.RISK_EVENTS,
        'assets_by_status': chariot.statistics.util.ASSETS_BY_STATUS,
        'assets_by_class': chariot.statistics.util.ASSETS_BY_CLASS,
        'seeds': chariot.statistics.util.SEEDS
    }

    # Use mapped filter if available, otherwise use raw filter string
    actual_filter = filter_map.get(filter, filter)

    render_list_results(
        chariot.statistics.list(
            actual_filter,
            from_date,
            to_date,
            offset,
            pagination_size(page)
        ),
        details
    )


@list.command()
@list_params('setting name')
def settings(chariot, filter, details, offset, page):
    """ List settings

    Retrieve and display a list of settings.

    \b
    Filtering options:
        - Use the --filter option to filter on the name of the setting.

    \b
    Example usages:
        - guard list settings
        - guard list settings --filter rate-limit
        - guard list settings --details
        - guard list settings --page all
    """
    render_list_results(chariot.settings.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('configuration name')
@praetorian_only
def configurations(chariot, filter, details, offset, page):
    """ List configurations

    Retrieve and display a list of configurations.

    \b
    Filtering options:
        - Use the --filter option to filter on the name of the configuration.

    \b
    Example usages:
        - guard list configurations
        - guard list configurations --filter nuclei
        - guard list configurations --details
        - guard list configurations --page all
    """
    render_list_results(chariot.configurations.list(filter, offset, pagination_size(page)), details)


@list.command()
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@pagination
@cli_handler
def keys(chariot, details, offset, page):
    """ List API keys

    Retrieve and display a list of API keys.

    \b
    Example usages:
        - guard list keys
        - guard list keys --details
        - guard list keys --page all
    """
    render_list_results(chariot.keys.list(offset, pagination_size(page)), details)

@list.command()
@list_params('credential ID', has_details=False, has_filter=False)
def credentials(chariot, offset, page):
    """ List credentials

    Retrieve and display a list of credentials.

    \b
    Example usages:
        - guard list credentials
        - guard list credentials --page all
    """
    print_json(chariot.credentials.list(offset, pagination_size(page)))


@list.command()
@cli_handler
@click.option('-n', '--name')
@click.option('-t', '--target')
@click.option('-e', '--executor')
def capabilities(chariot, name, target, executor):
    """ List capabilities

    Example usage:
        - guard list capabilities --name nuclei --target attribute --executor chariot
    """
    print_json(chariot.capabilities.list(name, target, executor))


@list.command()
@list_params('IP address')
def scanners(chariot, filter, details, offset, page):
    """ List scanners

    Retrieve and display a list of scanner records that track IP addresses used by Guard.

    \b
    Example usages:
        - guard list scanners
        - guard list scanners --filter 127.0.0.1
        - guard list scanners --details
        - guard list scanners --page all
    """
    render_list_results(chariot.scanners.list(filter, offset, pagination_size(page)), details)


@list.command()
@click.option('--parent', required=False, help='Optional WebApp key to filter pages')
@click.option('-f', '--filter', required=False, help='Optional URL to filter pages')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@pagination
@cli_handler
def webpages(chariot, parent, filter, details, offset, page):
    """ List WebPages

    Retrieve and display a list of pages/URLs. Can optionally filter by specific WebApplication.

    \b
    Example usages:
        - guard list webpages
        - guard list webpages --parent "#webapplication#https://app.example.com"
        - guard list webpages --filter /login
        - guard list webpages --parent "#webapplication#https://app.example.com" --details
        - guard list webpages --page all
    """
    render_list_results(chariot.webpage.list(parent, filter, offset, pagination_size(page)), details)


@list.command()
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@pagination
@cli_handler
def schedules(chariot, details, offset, page):
    """ List capability schedules

    Retrieve and display a list of scheduled capability executions.

    \b
    Example usages:
        - guard list schedules
        - guard list schedules --details
        - guard list schedules --page all
    """
    render_list_results(chariot.schedules.list(pagination_size(page)), details)
