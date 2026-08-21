import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


DAYS_OF_WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def _parse_weekly_schedule(days, time_str):
    """Build a weekly schedule dict from --days and --time flags."""
    enabled_days = {d.strip().lower() for d in days.split(',')} if days else set()
    invalid = enabled_days - set(DAYS_OF_WEEK)
    if invalid:
        error(f'Invalid day(s): {", ".join(sorted(invalid))}. Valid: {", ".join(DAYS_OF_WEEK)}')
        return {}
    schedule = {}
    for day in DAYS_OF_WEEK:
        if day in enabled_days:
            schedule[day] = {'enabled': True, 'time': time_str}
        else:
            schedule[day] = {'enabled': False, 'time': ''}
    return schedule


@chariot.group()
def schedule():
    """ Manage capability schedules """
    pass


@schedule.command()
@cli_handler
@click.option('--capability', required=True, help='Name of the capability to schedule')
@click.option('--target', required=True, help='Target asset key (e.g., #asset#hostname#hostname)')
@click.option('--days', required=True,
              help='Comma-separated days to run (e.g., monday,wednesday,friday)')
@click.option('--time', 'time_str', required=True, help='UTC time to run (HH:MM, e.g., 10:00)')
@click.option('--start-date', required=True, help='Start date in RFC3339 format (e.g., 2024-01-15T00:00:00Z)')
@click.option('--end-date', default=None, help='Optional end date in RFC3339 format')
@click.option('--config', 'config_json', default=None, help='Capability config as JSON string')
@click.option('--client-id', default=None, help='Aegis client ID for Aegis capabilities')
def create(sdk, capability, target, days, time_str, start_date, end_date, config_json, client_id):
    """ Create a new capability schedule

    \b
    Example usages:
        guard schedule create --capability nuclei --target "#asset#example.com#example.com" \\
            --days monday,friday --time 10:00 --start-date 2024-01-15T00:00:00Z
        guard schedule create --capability portscan --target "#asset#10.0.0.1#10.0.0.1" \\
            --days monday,tuesday,wednesday,thursday,friday --time 02:00 \\
            --start-date 2024-01-01T00:00:00Z --end-date 2024-12-31T23:59:59Z
    """
    weekly = _parse_weekly_schedule(days, time_str)
    config = None
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            error(f'Invalid JSON for --config: {e}')

    result = sdk.schedules.create(
        capability_name=capability,
        target_key=target,
        weekly_schedule=weekly,
        start_date=start_date,
        end_date=end_date,
        config=config,
        client_id=client_id,
    )
    print_json(result)


@schedule.command()
@cli_handler
@click.argument('schedule_id', required=True)
@click.option('--days', default=None,
              help='Comma-separated days to run (e.g., monday,wednesday,friday)')
@click.option('--time', 'time_str', default=None, help='UTC time to run (HH:MM)')
@click.option('--start-date', default=None, help='New start date in RFC3339 format')
@click.option('--end-date', default=None, help='New end date in RFC3339 format (empty string to clear)')
@click.option('--config', 'config_json', default=None, help='Capability config as JSON string')
def update(sdk, schedule_id, days, time_str, start_date, end_date, config_json):
    """ Update an existing capability schedule

    \b
    Argument:
        - SCHEDULE_ID: the ID of the schedule to update

    \b
    Example usages:
        guard schedule update abc123 --days monday,tuesday --time 14:00
        guard schedule update abc123 --end-date 2025-06-30T23:59:59Z
        guard schedule update abc123 --config '{"templates":"cves/"}'
    """
    weekly = None
    if days is not None:
        if days == '':
            # Explicit empty --days means "disable all days" -- --time is
            # not meaningful in that case, so don't require it.
            weekly = _parse_weekly_schedule(days, time_str or '')
        elif time_str is None:
            error('--time is required when --days is specified')
            return
        else:
            weekly = _parse_weekly_schedule(days, time_str)
    elif time_str is not None:
        error('--days is required when --time is specified')
        return

    config = None
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            error(f'Invalid JSON for --config: {e}')

    result = sdk.schedules.update(
        schedule_id=schedule_id,
        weekly_schedule=weekly,
        start_date=start_date,
        end_date=end_date,
        config=config,
    )
    print_json(result)


@schedule.command()
@cli_handler
@click.argument('schedule_id', required=True)
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def delete(sdk, schedule_id, force):
    """ Delete a capability schedule

    \b
    Argument:
        - SCHEDULE_ID: the ID of the schedule to delete

    \b
    Example usages:
        guard schedule delete abc123-def456
        guard schedule delete abc123-def456 --force
    """
    if not force:
        if not click.confirm(f'Delete schedule {schedule_id}?', default=False):
            click.echo('Cancelled.')
            return

    sdk.schedules.delete(schedule_id)
    click.echo(f'Schedule {schedule_id} deleted.')
