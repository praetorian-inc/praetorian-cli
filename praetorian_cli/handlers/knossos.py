"""Knossos — canary/deception environment CLI handler."""
import json
from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Status color mapping for environment display
_STATUS_COLORS = {
    'deployed': 'green',
    'pending': 'yellow',
    'provisioning': 'yellow',
    'failed': 'red',
    'error': 'red',
    'stopped': None,       # will use dim=True
    'destroying': 'yellow',
    'destroyed': None,
}


def _colorize_status(status):
    """Return a colored string for an environment status."""
    s = (status or 'unknown').lower()
    if s in ('stopped', 'destroyed', 'unknown'):
        return click.style(s, dim=True)
    color = _STATUS_COLORS.get(s, 'white')
    return click.style(s, fg=color)


def _sep(width=60):
    click.echo(click.style('─' * width, dim=True))


# ---------------------------------------------------------------------------
# Top-level group
# ---------------------------------------------------------------------------

@chariot.group('knossos')
def knossos():
    """Manage Knossos canary/deception environments.

    Knossos generates realistic-looking infrastructure that acts as
    honeypots, detecting unauthorized access and lateral movement.
    Canary environments blend in with real assets and alert on any
    interaction, providing early warning of attackers inside the network.

    \b
    Typical workflow:
        1. Create or infer a profile describing the environment shape.
        2. Generate an environment from that profile.
        3. Validate, then deploy the environment.
        4. Monitor events for canary signals.
    """
    pass


# ---------------------------------------------------------------------------
# profile sub-group
# ---------------------------------------------------------------------------

@knossos.group('profile')
def profile():
    """Manage the Knossos canary environment profile.

    A profile describes the type, shape, and configuration of canary
    infrastructure to generate. There is one active profile per account;
    use 'versions' to list historical snapshots.
    """
    pass


@profile.command('show')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def profile_show(sdk, json_output):
    """Show the current canary environment profile.

    \b
    Example usages:
        guard knossos profile show
        guard knossos profile show --json-output
    """
    result = sdk.get('knossos/profile')
    if json_output:
        print_json(result)
        return

    if not result:
        click.echo('No profile found. Use "guard knossos profile create" to create one.')
        return

    click.echo(click.style('Knossos Profile', bold=True))
    _sep()
    click.echo(f"Name:        {result.get('name', '—')}")
    click.echo(f"Description: {result.get('description', '—')}")
    click.echo(f"Version:     {result.get('version', '—')}")
    click.echo(f"Created:     {result.get('created_at', '—')}")
    click.echo(f"Updated:     {result.get('updated_at', '—')}")
    extra = {k: v for k, v in result.items()
             if k not in ('name', 'description', 'version', 'created_at', 'updated_at')}
    if extra:
        _sep()
        click.echo(json.dumps(extra, indent=2))


@profile.command('create')
@cli_handler
@click.option('--name', required=True, help='Profile name')
@click.option('--description', 'description', default='', help='Optional description')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def profile_create(sdk, name, description, json_output):
    """Create a new canary environment profile.

    \b
    Example usages:
        guard knossos profile create --name "corp-internal"
        guard knossos profile create --name "dmz-honeypot" --description "DMZ-facing canary cluster"
    """
    body = {'name': name}
    if description:
        body['description'] = description

    result = sdk.post('knossos/profile', body)
    click.echo(click.style('Profile created.', fg='green'))
    if json_output:
        print_json(result)
    else:
        click.echo(f"Name: {result.get('name', name)}")
        click.echo(f"Version: {result.get('version', '—')}")


@profile.command('update')
@cli_handler
@click.option('--field', required=True, help='Field name to update')
@click.option('--value', required=True, help='New value for the field')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def profile_update(sdk, field, value, json_output):
    """Update a field on the current canary environment profile.

    \b
    Example usages:
        guard knossos profile update --field name --value "new-profile-name"
        guard knossos profile update --field description --value "Updated description"
    """
    body = {field: value}
    result = sdk.put('knossos/profile', body)
    click.echo(click.style('Profile updated.', fg='green'))
    if json_output:
        print_json(result)
    else:
        click.echo(f"Field '{field}' set to '{value}'.")


@profile.command('delete')
@cli_handler
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def profile_delete(sdk, force):
    """Delete the current canary environment profile.

    \b
    Example usages:
        guard knossos profile delete
        guard knossos profile delete --force
    """
    if not force:
        click.confirm('Delete the current Knossos profile? This cannot be undone.', abort=True)

    sdk.delete('knossos/profile', {}, {})
    click.echo(click.style('Profile deleted.', fg='yellow'))


@profile.command('infer')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def profile_infer(sdk, json_output):
    """Infer a canary profile from existing assets in the engagement.

    Analyzes discovered assets and auto-generates a profile that mirrors
    the real environment, making the canaries blend in convincingly.

    \b
    Example usages:
        guard knossos profile infer
        guard knossos profile infer --json-output
    """
    click.echo('Inferring profile from existing assets...', err=True)
    result = sdk.post('knossos/profile/infer', {})
    click.echo(click.style('Profile inferred.', fg='green'))
    if json_output:
        print_json(result)
    else:
        click.echo(f"Name: {result.get('name', '—')}")
        click.echo(f"Version: {result.get('version', '—')}")
        inferred = result.get('inferred_from', 0)
        if inferred:
            click.echo(f"Inferred from {inferred} asset(s).")


@profile.command('versions')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def profile_versions(sdk, json_output):
    """List historical versions of the canary environment profile.

    \b
    Example usages:
        guard knossos profile versions
        guard knossos profile versions --json-output
    """
    result = sdk.get('knossos/profile/versions')
    if json_output:
        print_json(result)
        return

    versions = result if isinstance(result, list) else result.get('versions', [])
    if not versions:
        click.echo('No profile versions found.')
        return

    click.echo(click.style(f'{"Version":<10} {"Created":<28} {"Name"}', bold=True))
    _sep()
    for v in versions:
        ver = str(v.get('version', '—'))
        created = v.get('created_at', '—')
        name = v.get('name', '—')
        click.echo(f'{ver:<10} {created:<28} {name}')


# ---------------------------------------------------------------------------
# environment sub-group
# ---------------------------------------------------------------------------

@knossos.group('environment')
def environment():
    """Manage Knossos canary environments.

    Environments are deployable honeypot configurations generated from a
    profile. Each environment can be deployed to cloud infrastructure,
    monitored for access events, and torn down when no longer needed.
    """
    pass


@environment.command('list')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_list(sdk, json_output):
    """List all Knossos canary environments.

    \b
    Example usages:
        guard knossos environment list
        guard knossos environment list --json-output
    """
    result = sdk.get('knossos/environments')
    if json_output:
        print_json(result)
        return

    environments = result if isinstance(result, list) else result.get('environments', [])
    if not environments:
        click.echo('No environments found. Use "guard knossos environment generate" to create one.')
        return

    click.echo(click.style(f'{"ID":<36} {"Status":<14} {"Name"}', bold=True))
    _sep()
    for env in environments:
        env_id = env.get('id', '—')
        status = env.get('status', 'unknown')
        name = env.get('name', '—')
        click.echo(f'{env_id:<36} {_colorize_status(status):<23} {name}')


@environment.command('show')
@cli_handler
@click.argument('id')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_show(sdk, id, json_output):
    """Show details for a specific environment.

    \b
    Example usages:
        guard knossos environment show <environment-id>
        guard knossos environment show <environment-id> --json-output
    """
    result = sdk.get(f'knossos/environment/{quote(id, safe="")}')
    if json_output:
        print_json(result)
        return

    if not result:
        error(f'Environment not found: {id}')

    click.echo(click.style('Knossos Environment', bold=True))
    _sep()
    click.echo(f"ID:          {result.get('id', id)}")
    click.echo(f"Name:        {result.get('name', '—')}")
    click.echo(f"Status:      {_colorize_status(result.get('status', 'unknown'))}")
    click.echo(f"Profile:     {result.get('profile', '—')}")
    click.echo(f"Created:     {result.get('created_at', '—')}")
    click.echo(f"Updated:     {result.get('updated_at', '—')}")
    extra = {k: v for k, v in result.items()
             if k not in ('id', 'name', 'status', 'profile', 'created_at', 'updated_at')}
    if extra:
        _sep()
        click.echo(json.dumps(extra, indent=2))


@environment.command('generate')
@cli_handler
@click.option('--profile', 'profile_name', required=True, help='Profile name or version to generate from')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_generate(sdk, profile_name, json_output):
    """Generate a new canary environment from a profile.

    Creates the environment configuration but does not deploy it.
    Use 'validate' then 'deploy' to bring it online.

    \b
    Example usages:
        guard knossos environment generate --profile corp-internal
        guard knossos environment generate --profile corp-internal --json-output
    """
    body = {'profile': profile_name}
    click.echo('Generating environment...', err=True)
    result = sdk.post('knossos/environment/generate', body)
    click.echo(click.style('Environment generated.', fg='green'))
    if json_output:
        print_json(result)
    else:
        click.echo(f"ID:     {result.get('id', '—')}")
        click.echo(f"Name:   {result.get('name', '—')}")
        click.echo(f"Status: {_colorize_status(result.get('status', 'pending'))}")
        click.echo()
        click.echo(click.style("Next steps:", dim=True))
        click.echo(f"  guard knossos environment validate {result.get('id', '<id>')}")
        click.echo(f"  guard knossos environment deploy   {result.get('id', '<id>')}")


@environment.command('delete')
@cli_handler
@click.argument('id')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def environment_delete(sdk, id, force):
    """Delete a canary environment.

    \b
    Example usages:
        guard knossos environment delete <environment-id>
        guard knossos environment delete <environment-id> --force
    """
    if not force:
        click.confirm(f'Delete environment {id}? This cannot be undone.', abort=True)

    sdk.delete(f'knossos/environment/{quote(id, safe="")}', {}, {})
    click.echo(click.style(f'Environment {id} deleted.', fg='yellow'))


@environment.command('validate')
@cli_handler
@click.argument('id')
def environment_validate(sdk, id):
    """Validate a canary environment configuration before deployment.

    Checks that the environment config is complete and deployable without
    actually provisioning any infrastructure.

    \b
    Example usages:
        guard knossos environment validate <environment-id>
    """
    click.echo(f'Validating environment {id}...', err=True)
    result = sdk.post(f'knossos/environment/{quote(id, safe="")}/validate', {})

    valid = result.get('valid', result.get('status') == 'ok') if result else False
    if valid:
        click.echo(click.style('Validation passed.', fg='green'))
    else:
        issues = result.get('issues', result.get('errors', [])) if result else []
        click.echo(click.style('Validation failed.', fg='red'))
        for issue in issues:
            click.echo(f'  - {issue}')
        if not issues:
            print_json(result)


@environment.command('deploy')
@cli_handler
@click.argument('id')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_deploy(sdk, id, json_output):
    """Deploy a canary environment to infrastructure.

    Initiates deployment. Use 'status' to poll until deployment completes.

    \b
    Example usages:
        guard knossos environment deploy <environment-id>
        guard knossos environment deploy <environment-id> --json-output
    """
    click.echo(f'Deploying environment {id}...', err=True)
    result = sdk.post(f'knossos/environment/{quote(id, safe="")}/deploy', {})
    click.echo(click.style('Deployment initiated.', fg='green'))
    if json_output:
        print_json(result)
    else:
        click.echo(f"Status: {_colorize_status(result.get('status', 'pending') if result else 'pending')}")
        click.echo()
        click.echo(click.style("Monitor progress with:", dim=True))
        click.echo(f"  guard knossos environment status {id}")


@environment.command('status')
@cli_handler
@click.argument('id')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_status(sdk, id, json_output):
    """Get the deployment status of a canary environment.

    \b
    Example usages:
        guard knossos environment status <environment-id>
        guard knossos environment status <environment-id> --json-output
    """
    result = sdk.get(f'knossos/environment/{quote(id, safe="")}/status')
    if json_output:
        print_json(result)
        return

    if not result:
        error(f'No status found for environment: {id}')

    status = result.get('status', 'unknown')
    click.echo(f"Environment: {id}")
    click.echo(f"Status:      {_colorize_status(status)}")
    message = result.get('message', '')
    if message:
        click.echo(f"Message:     {message}")
    progress = result.get('progress')
    if progress is not None:
        click.echo(f"Progress:    {progress}%")
    updated = result.get('updated_at', '')
    if updated:
        click.echo(f"Updated:     {updated}")


@environment.command('events')
@cli_handler
@click.argument('id')
@click.option('--limit', default=50, type=int, show_default=True, help='Maximum number of events to return')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_events(sdk, id, limit, json_output):
    """Get canary signal events for an environment.

    Events are triggered whenever someone interacts with a canary asset,
    indicating potential unauthorized access or lateral movement.

    \b
    Example usages:
        guard knossos environment events <environment-id>
        guard knossos environment events <environment-id> --limit 100
        guard knossos environment events <environment-id> --json-output
    """
    result = sdk.get(f'knossos/environment/{quote(id, safe="")}/events')
    if json_output:
        print_json(result)
        return

    events = result if isinstance(result, list) else result.get('events', [])
    events = events[:limit]

    if not events:
        click.echo('No events recorded for this environment.')
        return

    click.echo(click.style(f'{"Timestamp":<28} {"Type":<20} {"Source"}', bold=True))
    _sep()
    for evt in events:
        ts = evt.get('timestamp', evt.get('created_at', '—'))
        evt_type = evt.get('type', evt.get('event_type', '—'))
        source = evt.get('source', evt.get('source_ip', '—'))
        colored_type = click.style(evt_type, fg='red', bold=True) if evt_type != '—' else '—'
        click.echo(f'{ts:<28} {colored_type:<29} {source}')

    click.echo()
    click.echo(click.style(f'{len(events)} event(s) shown.', dim=True))


@environment.command('cost')
@cli_handler
@click.argument('id')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def environment_cost(sdk, id, json_output):
    """Get estimated cost for a canary environment.

    \b
    Example usages:
        guard knossos environment cost <environment-id>
        guard knossos environment cost <environment-id> --json-output
    """
    result = sdk.get(f'knossos/environment/{quote(id, safe="")}/cost')
    if json_output:
        print_json(result)
        return

    if not result:
        error(f'No cost data found for environment: {id}')

    click.echo(click.style('Estimated Cost', bold=True))
    _sep()
    click.echo(f"Environment:  {id}")
    click.echo(f"Monthly:      {result.get('monthly', result.get('monthly_cost', '—'))}")
    click.echo(f"Hourly:       {result.get('hourly', result.get('hourly_cost', '—'))}")
    currency = result.get('currency', 'USD')
    click.echo(f"Currency:     {currency}")
    breakdown = result.get('breakdown', [])
    if breakdown:
        _sep()
        click.echo(click.style('Breakdown:', bold=True))
        for item in breakdown:
            name = item.get('name', item.get('resource', '—'))
            cost = item.get('cost', item.get('monthly_cost', '—'))
            click.echo(f"  {name:<30} {cost}")


@environment.command('emit')
@cli_handler
@click.argument('id')
@click.option('--signal', required=True, help='Signal type to emit (e.g., access, credential-use, lateral-movement)')
@click.option('--data', default=None, help='Optional JSON data payload for the signal')
def environment_emit(sdk, id, signal, data):
    """Emit a canary signal for an environment.

    Used for testing alert pipelines or simulating canary triggers.

    \b
    Example usages:
        guard knossos environment emit <environment-id> --signal access
        guard knossos environment emit <environment-id> --signal credential-use --data '{"username":"admin"}'
    """
    body = {'signal': signal}
    if data:
        try:
            body['data'] = json.loads(data)
        except json.JSONDecodeError:
            error(f'--data must be valid JSON. Got: {data}')

    result = sdk.post(f'knossos/environment/{quote(id, safe="")}/emit', body)
    click.echo(click.style(f'Signal "{signal}" emitted.', fg='green'))
    if result:
        print_json(result)
