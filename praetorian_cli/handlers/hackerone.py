from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Severity rating color mapping
SEVERITY_COLORS = {
    'critical': 'red',
    'high': 'bright_red',
    'medium': 'yellow',
    'low': 'green',
    'none': 'white',
}

# Program state color mapping
STATE_COLORS = {
    'public_mode': 'green',
    'soft_launched': 'yellow',
    'invite_only': 'cyan',
    'disabled': 'red',
}


@chariot.group('hackerone')
def hackerone():
    """Manage HackerOne bug bounty integration.

    Sync scope, manage reports, and interact with HackerOne programs.
    Use these commands to bridge Guard assets with your HackerOne program
    workflow — from seeding discovered assets to triaging report severity.
    """


@hackerone.command('programs')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON instead of formatted table')
def programs(sdk, json_output):
    """List available HackerOne programs.

    Fetches all HackerOne programs accessible to the current account and
    displays their handle, name, and enrollment state.

    \b
    Example usages:
        guard hackerone programs
        guard hackerone programs --json-output
    """
    result = sdk.get('hackerone/programs')
    if json_output:
        print_json(result)
        return

    program_list = result if isinstance(result, list) else result.get('programs', result.get('data', []))
    if not program_list:
        click.echo('No programs found.')
        return

    click.echo(click.style(f'{"HANDLE":<30}  {"NAME":<40}  STATE', bold=True))
    click.echo(click.style('─' * 85, dim=True))
    for prog in program_list:
        handle = prog.get('handle', prog.get('id', ''))
        name = prog.get('name', prog.get('attributes', {}).get('name', ''))
        state = prog.get('state', prog.get('attributes', {}).get('state', 'unknown'))
        state_color = STATE_COLORS.get(state, 'white')
        click.echo(
            click.style(f'{str(handle):<30}', fg='cyan') +
            f'  {str(name):<40}  ' +
            click.style(state, fg=state_color)
        )


@hackerone.command('program')
@cli_handler
@click.argument('handle')
@click.option('--section', type=click.Choice(['scope', 'reports']), default='scope',
              show_default=True, help='Program sub-section to retrieve')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON instead of formatted output')
def program(sdk, handle, section, json_output):
    """Get details for a specific HackerOne program.

    Fetches the given HANDLE's scope or reports section from the Guard
    HackerOne integration. Use --section to select the sub-resource.

    \b
    Example usages:
        guard hackerone program acme-corp
        guard hackerone program acme-corp --section reports
        guard hackerone program acme-corp --section scope --json-output
    """
    result = sdk.get(f'hackerone/programs/{quote(handle, safe="")}/{quote(section, safe="")}')
    if json_output:
        print_json(result)
        return

    if section == 'scope':
        _render_scope(result)
    else:
        _render_reports(result)


@hackerone.command('sync-scope')
@cli_handler
@click.option('--program', 'program_handle', required=True, help='HackerOne program handle to sync')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def sync_scope(sdk, program_handle, json_output):
    """Sync HackerOne program scope into Guard seeds and assets.

    Posts the program's in-scope targets to the Guard backend, which
    resolves them as seeds and assets for continuous monitoring. Run this
    after joining a new program or when scope changes.

    \b
    Example usages:
        guard hackerone sync-scope --program acme-corp
        guard hackerone sync-scope --program acme-corp --json-output
    """
    body = {'program': program_handle}
    result = sdk.post('hackerone/sync-scope', body)
    if json_output:
        print_json(result)
        return

    seeded = result.get('seeded', result.get('count', 0)) if isinstance(result, dict) else 0
    click.echo(
        click.style('Scope synced: ', bold=True) +
        click.style(program_handle, fg='cyan') +
        f'  ({seeded} item{"s" if seeded != 1 else ""} imported)'
    )


@hackerone.command('activities')
@cli_handler
@click.option('--program', 'program_handle', default=None, help='Filter activities to a specific program handle')
@click.option('--limit', default=25, show_default=True, type=int, help='Maximum number of activities to return')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON instead of formatted output')
def activities(sdk, program_handle, limit, json_output):
    """View HackerOne activities.

    Retrieves recent activity events from HackerOne. Optionally filter by
    program handle and cap results with --limit.

    \b
    Example usages:
        guard hackerone activities
        guard hackerone activities --program acme-corp
        guard hackerone activities --limit 50
        guard hackerone activities --program acme-corp --limit 10 --json-output
    """
    path = 'hackerone/activities'
    query_params = {}
    if program_handle:
        query_params['program'] = program_handle
    if limit:
        query_params['limit'] = str(limit)

    if query_params:
        qs = '&'.join(f'{k}={quote(v, safe="")}' for k, v in query_params.items())
        path = f'{path}?{qs}'

    result = sdk.get(path)
    if json_output:
        print_json(result)
        return

    activity_list = result if isinstance(result, list) else result.get('activities', result.get('data', []))
    if not activity_list:
        click.echo('No activities found.')
        return

    for item in activity_list[:limit]:
        _render_activity(item)


@hackerone.command('comment')
@cli_handler
@click.option('--report-id', required=True, help='HackerOne report ID to comment on')
@click.option('--body', 'comment_body', required=True, help='Comment text to post')
def comment(sdk, report_id, comment_body):
    """Post a comment on a HackerOne report.

    Submits a comment to the specified HackerOne report via the Guard
    integration. The comment is posted as the authenticated user.

    \b
    Example usages:
        guard hackerone comment --report-id 1234567 --body "Triaging this now."
        guard hackerone comment --report-id 1234567 --body "Confirmed — patched in v2.3.1."
    """
    body = {
        'report_id': report_id,
        'body': comment_body,
    }
    result = sdk.post('hackerone/comment', body)
    click.echo(
        click.style('Comment posted on report ', bold=False) +
        click.style(f'#{report_id}', fg='cyan', bold=True)
    )
    if result:
        print_json(result)


@hackerone.command('severity')
@cli_handler
@click.option('--report-id', required=True, help='HackerOne report ID to update')
@click.option('--rating', required=True,
              type=click.Choice(['critical', 'high', 'medium', 'low', 'none']),
              help='Severity rating to apply to the report')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def severity(sdk, report_id, rating, json_output):
    """Update severity on a HackerOne report.

    Sets the severity rating for the given report ID. This translates to
    the HackerOne severity field and triggers a re-triage notification.

    \b
    Example usages:
        guard hackerone severity --report-id 1234567 --rating critical
        guard hackerone severity --report-id 1234567 --rating medium --json-output
    """
    body = {
        'report_id': report_id,
        'rating': rating,
    }
    result = sdk.put('hackerone/severity', body)
    if json_output:
        print_json(result)
        return

    color = SEVERITY_COLORS.get(rating, 'white')
    click.echo(
        click.style('Severity updated: ', bold=True) +
        click.style(f'#{report_id}', fg='cyan') +
        '  ' +
        click.style(rating.upper(), fg=color, bold=True)
    )


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------

def _render_scope(result):
    """Render program scope as a table."""
    scope_list = result if isinstance(result, list) else result.get('scope', result.get('data', []))
    if not scope_list:
        click.echo('No scope entries found.')
        return

    click.echo(click.style(f'{"TYPE":<12}  {"ASSET":<50}  ELIGIBLE', bold=True))
    click.echo(click.style('─' * 75, dim=True))
    for entry in scope_list:
        asset_type = entry.get('asset_type', entry.get('type', ''))
        asset_id = entry.get('asset_identifier', entry.get('asset', entry.get('id', '')))
        eligible = entry.get('eligible_for_bounty', entry.get('bounty_eligible', False))
        eligible_str = click.style('yes', fg='green') if eligible else click.style('no', fg='red')
        click.echo(f'{str(asset_type):<12}  {str(asset_id):<50}  {eligible_str}')


def _render_reports(result):
    """Render program reports as a brief list."""
    report_list = result if isinstance(result, list) else result.get('reports', result.get('data', []))
    if not report_list:
        click.echo('No reports found.')
        return

    click.echo(click.style(f'{"ID":<12}  {"STATE":<15}  {"SEVERITY":<10}  TITLE', bold=True))
    click.echo(click.style('─' * 80, dim=True))
    for rpt in report_list:
        attrs = rpt.get('attributes', rpt)
        report_id = rpt.get('id', '')
        title = attrs.get('title', '')
        state = attrs.get('state', '')
        sev = attrs.get('severity_rating', attrs.get('severity', 'none'))
        sev_color = SEVERITY_COLORS.get(str(sev).lower(), 'white')
        click.echo(
            click.style(f'{str(report_id):<12}', fg='cyan') +
            f'  {str(state):<15}  ' +
            click.style(f'{str(sev):<10}', fg=sev_color) +
            f'  {title}'
        )


def _render_activity(item):
    """Render a single activity event."""
    attrs = item.get('attributes', item)
    activity_type = attrs.get('type', attrs.get('activity_type', 'activity'))
    created_at = attrs.get('created_at', '')
    actor = attrs.get('actor', {})
    actor_name = actor.get('username', actor.get('name', '')) if isinstance(actor, dict) else str(actor)
    message = attrs.get('message', attrs.get('body', ''))

    prefix = click.style(f'[{activity_type}]', fg='cyan')
    timestamp = click.style(f' {created_at}', dim=True) if created_at else ''
    by = click.style(f' by {actor_name}', fg='yellow') if actor_name else ''
    click.echo(f'{prefix}{timestamp}{by}')
    if message:
        # Indent message body
        for line in str(message).splitlines():
            click.echo(f'    {line}')
    click.echo()
