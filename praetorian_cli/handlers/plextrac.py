from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group('plextrac', deprecated=True)
def plextrac():
    """[DEPRECATED] PlexTrac integration — no longer in use.

    \b
    This integration has been deprecated. Use Guard's native reporting instead:
        guard export report --title "Report" --client-name "Acme"
        guard report generate --title "Report" --client "Acme"
    """
    pass


# ---------------------------------------------------------------------------
# guard plextrac reporting  (sub-group)
# ---------------------------------------------------------------------------

@plextrac.group('reporting')
def reporting():
    """Manage the PlexTrac reporting configuration for this account."""
    pass


@reporting.command('show')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def reporting_show(sdk, json_output):
    """Show the current PlexTrac reporting configuration.

    Displays the PlexTrac instance URL and whether an API key is configured.
    The API key value is never returned by the server.

    \b
    Example usages:
        guard plextrac reporting show
        guard plextrac reporting show --json-output
    """
    result = sdk.get('plextrac/reporting')

    if not result:
        click.echo(click.style('No PlexTrac reporting configuration found.', fg='yellow'))
        return

    if json_output:
        print_json(result)
        return

    click.echo(click.style('PlexTrac Reporting Configuration', bold=True))
    click.echo(click.style('─' * 40, dim=True))
    click.echo(f"  Instance URL : {result.get('instance_url', '—')}")
    click.echo(f"  API Key      : {'(configured)' if result.get('api_key_set') else '(not set)'}")
    created = result.get('created')
    if created:
        click.echo(f"  Created      : {created}")
    updated = result.get('updated')
    if updated:
        click.echo(f"  Updated      : {updated}")


@reporting.command('configure')
@cli_handler
@click.option('--instance-url', required=True, help='PlexTrac instance URL (e.g. https://yourorg.plextrac.com)')
@click.option('--api-key', required=True, help='PlexTrac API key')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def reporting_configure(sdk, instance_url, api_key, json_output):
    """Configure the PlexTrac instance URL and API key.

    Creates the configuration if it does not exist, otherwise updates it.
    The API key is stored server-side and never echoed back.

    \b
    Example usages:
        guard plextrac reporting configure --instance-url https://acme.plextrac.com --api-key <KEY>
        guard plextrac reporting configure --instance-url https://acme.plextrac.com --api-key <KEY> --json-output
    """
    body = {
        'instance_url': instance_url,
        'api_key': api_key,
    }

    # Try PUT first (update), fall back to POST (create) on 404-style responses.
    # Guard returns the upserted object regardless; we use POST here because the
    # route semantics follow a create-or-update pattern.
    existing = sdk.get('plextrac/reporting')
    if existing:
        result = sdk.put('plextrac/reporting', body)
        action = 'updated'
    else:
        result = sdk.post('plextrac/reporting', body)
        action = 'created'

    if json_output:
        print_json(result)
        return

    click.echo(
        click.style('✓ ', fg='green') +
        f'PlexTrac reporting configuration {action}.'
    )
    click.echo(f"  Instance URL : {instance_url}")


@reporting.command('delete')
@cli_handler
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def reporting_delete(sdk, force):
    """Delete the PlexTrac reporting configuration.

    Removes the stored instance URL and API key from Guard. This does not
    affect any data inside PlexTrac itself.

    \b
    Example usages:
        guard plextrac reporting delete
        guard plextrac reporting delete --force
    """
    if not force:
        click.confirm('Delete PlexTrac reporting configuration?', abort=True)
    sdk.delete('plextrac/reporting', {}, {})
    click.echo(click.style('✓ ', fg='green') + 'PlexTrac reporting configuration deleted.')


# ---------------------------------------------------------------------------
# guard plextrac export
# ---------------------------------------------------------------------------

@plextrac.command('export')
@cli_handler
@click.option('--report-id', required=True, help='Guard report ID to export findings from')
@click.option('--status-filter', default='', help='Filter findings by status before exporting (e.g. "OH")')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def export(sdk, report_id, status_filter, json_output):
    """Export Guard findings to a connected PlexTrac report.

    The Guard report must already be connected to a PlexTrac report via
    "guard plextrac connect" before findings can be exported. Optionally
    filter which findings are exported by status code.

    \b
    Status filter examples:
        OH   — Open High
        OC   — Open Critical
        OL   — Open Low

    \b
    Example usages:
        guard plextrac export --report-id abc123
        guard plextrac export --report-id abc123 --status-filter OH
        guard plextrac export --report-id abc123 --json-output
    """
    body = {'report_id': report_id}
    if status_filter:
        body['status_filter'] = status_filter

    result = sdk.post('plextrac/export', body)

    if json_output:
        print_json(result)
        return

    exported = result.get('exported', 0) if result else 0
    click.echo(
        click.style('✓ ', fg='green') +
        f'Exported {exported} finding(s) to PlexTrac.'
    )
    if result and result.get('plextrac_report_id'):
        click.echo(f"  PlexTrac Report ID : {result['plextrac_report_id']}")
    if result and result.get('errors'):
        click.echo(click.style(f"  Warnings: {len(result['errors'])} finding(s) could not be exported.", fg='yellow'))


# ---------------------------------------------------------------------------
# guard plextrac connect
# ---------------------------------------------------------------------------

@plextrac.command('connect')
@cli_handler
@click.option('--guard-report-id', required=True, help='Guard report ID')
@click.option('--plextrac-report-id', required=True, help='PlexTrac report ID to link to')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def connect(sdk, guard_report_id, plextrac_report_id, json_output):
    """Connect a Guard report to a PlexTrac report.

    Once connected, findings from the Guard report can be exported to the
    specified PlexTrac report using "guard plextrac export".

    \b
    Example usages:
        guard plextrac connect --guard-report-id abc123 --plextrac-report-id pt-456
        guard plextrac connect --guard-report-id abc123 --plextrac-report-id pt-456 --json-output
    """
    body = {
        'guard_report_id': guard_report_id,
        'plextrac_report_id': plextrac_report_id,
    }

    result = sdk.post('plextrac/reports/connect', body)

    if json_output:
        print_json(result)
        return

    click.echo(
        click.style('✓ ', fg='green') +
        f'Guard report {click.style(guard_report_id, bold=True)} connected to '
        f'PlexTrac report {click.style(plextrac_report_id, bold=True)}.'
    )


# ---------------------------------------------------------------------------
# guard plextrac definition  (sub-group)
# ---------------------------------------------------------------------------

@plextrac.group('definition')
def definition():
    """Manage PlexTrac finding definition templates.

    Definitions are reusable templates that map a Guard finding key to a
    PlexTrac finding title, body, and severity. They are used automatically
    during export to populate PlexTrac finding fields.
    """
    pass


@definition.command('list')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def definition_list(sdk, json_output):
    """List all PlexTrac finding definition templates.

    \b
    Example usages:
        guard plextrac definition list
        guard plextrac definition list --json-output
    """
    result = sdk.get('plextrac/definition')

    if json_output:
        print_json(result)
        return

    items = result if isinstance(result, list) else result.get('definitions', []) if result else []

    if not items:
        click.echo(click.style('No finding definitions found.', fg='yellow'))
        return

    click.echo(click.style(f'{"KEY":<35} {"TITLE":<40} {"SEVERITY"}', bold=True))
    click.echo(click.style('─' * 90, dim=True))
    for item in items:
        key = item.get('key', '')
        title = item.get('title', '')
        severity = item.get('severity', '')
        click.echo(f'{key:<35} {title:<40} {severity}')


@definition.command('show')
@cli_handler
@click.option('--key', required=True, help='Definition key to retrieve')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def definition_show(sdk, key, json_output):
    """Show a single PlexTrac finding definition by key.

    \b
    Example usages:
        guard plextrac definition show --key sqli
        guard plextrac definition show --key sqli --json-output
    """
    result = sdk.get(f'plextrac/definition?key={quote(key, safe="")}')

    if not result:
        error(f'No definition found for key: {key}')

    if json_output:
        print_json(result)
        return

    item = result[0] if isinstance(result, list) else result

    click.echo(click.style('PlexTrac Finding Definition', bold=True))
    click.echo(click.style('─' * 40, dim=True))
    click.echo(f"  Key      : {item.get('key', '—')}")
    click.echo(f"  Title    : {item.get('title', '—')}")
    click.echo(f"  Severity : {item.get('severity', '—')}")
    click.echo(f"  Body     :")
    body_text = item.get('body', '')
    for line in body_text.splitlines():
        click.echo(f'    {line}')


@definition.command('create')
@cli_handler
@click.option('--key', required=True, help='Unique identifier for this definition (e.g. sqli, xss)')
@click.option('--title', required=True, help='Finding title as it will appear in PlexTrac')
@click.option('--body', required=True, help='Finding description / narrative body text')
@click.option('--severity', default='', help='Severity label (e.g. Critical, High, Medium, Low, Informational)')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def definition_create(sdk, key, title, body, severity, json_output):
    """Create a new PlexTrac finding definition template.

    \b
    Example usages:
        guard plextrac definition create --key sqli --title "SQL Injection" --body "The application..." --severity High
        guard plextrac definition create --key xss --title "Cross-Site Scripting" --body "..." --json-output
    """
    payload = {
        'key': key,
        'title': title,
        'body': body,
    }
    if severity:
        payload['severity'] = severity

    result = sdk.post('plextrac/definition', payload)

    if json_output:
        print_json(result)
        return

    click.echo(
        click.style('✓ ', fg='green') +
        f'Definition {click.style(key, bold=True)} created.'
    )


@definition.command('update')
@cli_handler
@click.option('--key', required=True, help='Key of the definition to update')
@click.option('--title', default=None, help='New finding title')
@click.option('--body', default=None, help='New finding body text')
@click.option('--severity', default=None, help='New severity label')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def definition_update(sdk, key, title, body, severity, json_output):
    """Update an existing PlexTrac finding definition template.

    Only the fields you supply will be changed. At least one of --title,
    --body, or --severity must be provided.

    \b
    Example usages:
        guard plextrac definition update --key sqli --severity Critical
        guard plextrac definition update --key sqli --title "SQL Injection (Updated)" --body "New narrative..."
        guard plextrac definition update --key sqli --severity High --json-output
    """
    payload = {'key': key}
    if title is not None:
        payload['title'] = title
    if body is not None:
        payload['body'] = body
    if severity is not None:
        payload['severity'] = severity

    if len(payload) == 1:
        error('Provide at least one of --title, --body, or --severity to update.')

    result = sdk.put('plextrac/definition', payload)

    if json_output:
        print_json(result)
        return

    click.echo(
        click.style('✓ ', fg='green') +
        f'Definition {click.style(key, bold=True)} updated.'
    )


@definition.command('delete')
@cli_handler
@click.option('--key', required=True, help='Key of the definition to delete')
def definition_delete(sdk, key):
    """Delete a PlexTrac finding definition template.

    This only removes the local Guard template; it does not affect any
    findings already exported to PlexTrac.

    \b
    Example usages:
        guard plextrac definition delete --key sqli
    """
    sdk.delete('plextrac/definition', {'key': key}, {})
    click.echo(
        click.style('✓ ', fg='green') +
        f'Definition {click.style(key, bold=True)} deleted.'
    )
