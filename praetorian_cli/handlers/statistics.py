import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, pagination
from praetorian_cli.handlers.utils import render_list_results, pagination_size


@chariot.command()
@click.option('-f', '--filter', default='', help='Filter by statistic type or name')
@click.option('--from', 'from_date', help='Start date (YYYY-MM-DD)')
@click.option('--to', 'to_date', help='End date (YYYY-MM-DD)')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@pagination
@click.option('--help-stats', is_flag=True, help='Show detailed information about statistic types')
@cli_handler
def statistics(chariot, filter, from_date, to_date, details, offset, page, help_stats):
    """ List statistics
    Retrieve and display a list of statistics with optional date range filtering.
    Use --help-stats for detailed information about available statistic types.
    \b
    Example usages:
        - praetorian chariot statistics
        - praetorian chariot statistics --filter "my#status"
        - praetorian chariot statistics --from 2025-01-01 --to 2024-01-31
        - praetorian chariot statistics --details
        - praetorian chariot statistics --page all
        - praetorian chariot statistics --help-stats
    """
    if help_stats:
        click.echo(chariot.stats.util.get_statistics_help())
        return

    # Map common filter aliases to StatsFilter values
    filter_map = {
        'risks': chariot.stats.util.RISKS,
        'risk_events': chariot.stats.util.RISK_EVENTS,
        'assets_by_status': chariot.stats.util.ASSETS_BY_STATUS,
        'assets_by_class': chariot.stats.util.ASSETS_BY_CLASS,
        'seeds': chariot.stats.util.SEEDS
    }

    # Use mapped filter if available, otherwise use raw filter string
    actual_filter = filter_map.get(filter, filter)

    render_list_results(
        chariot.stats.list(
            actual_filter,
            from_date,
            to_date,
            offset,
            pagination_size(page)
        ),
        details
    )
