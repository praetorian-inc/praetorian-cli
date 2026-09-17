import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, render_list_results, pagination_size
from praetorian_cli.sdk.model.aegis import is_v2_agent
from praetorian_cli.ui.conversation.endpoint_status import (
    format_endpoint_execution_status,
)


@chariot.group()
def hunt():
    """Manage Hannibal hunts — launch, monitor, and control automated vulnerability discovery."""
    pass


def _internal_hunt_endpoint(
    sdk,
    endpoint_id,
    internal_hunt,
    agent,
    scope,
    confirm_endpoint,
):
    if not internal_hunt:
        if endpoint_id or confirm_endpoint:
            raise click.UsageError(
                '--endpoint and --confirm-endpoint require --internal'
            )
        return None
    if agent != 'hannibal':
        raise click.UsageError(
            '--internal requires the hannibal infrastructure agent'
        )
    if not scope:
        raise click.UsageError('--internal requires at least one --scope')

    endpoints = [
        candidate for candidate in sdk.aegis.list_hunt_endpoints()
        if is_v2_agent(candidate)
        and str(getattr(candidate, 'kind', '')).lower() == 'aegis'
    ]
    if not endpoints:
        raise click.ClickException(
            'No authorized Aegis v2 endpoints are available for this account.'
        )

    requested = (endpoint_id or '').strip().lower()
    if requested:
        id_match = next(
            (
                endpoint for endpoint in endpoints
                if endpoint.display_id.lower() == requested
            ),
            None,
        )
        if id_match:
            return id_match

        matches = [
            endpoint for endpoint in endpoints
            if (endpoint.hostname or '').lower() == requested
        ]
        if not matches:
            raise click.ClickException(
                f'Aegis v2 endpoint {endpoint_id!r} was not found.'
            )
        if len(matches) > 1:
            raise click.ClickException(
                f'Aegis v2 endpoint hostname {endpoint_id!r} is ambiguous; '
                'use its endpoint ID.'
            )
        return matches[0]

    click.echo('Authorized Aegis v2 endpoints:')
    for index, endpoint in enumerate(endpoints, 1):
        state = 'online' if endpoint.is_online else 'offline'
        click.echo(
            f'  {index}. {endpoint.hostname or "Unknown"} '
            f'({endpoint.display_id}, {state})'
        )
    selection = click.prompt(
        'Select endpoint',
        type=click.IntRange(1, len(endpoints)),
    )
    return endpoints[selection - 1]


@hunt.command()
@cli_handler
@click.option('-p', '--prompt', required=True, help='The hunt objective / central mandate')
@click.option('-e', '--expires', type=click.IntRange(1, 72), default=72, show_default=True,
              help='Hours until the hunt expires (1-72)')
@click.option('-a', '--agent', type=click.Choice(['hannibal', 'hannibal-cloud', 'hannibal-webapp', 'hannibal-llm']),
              default='hannibal', show_default=True, help='Agent type')
@click.option('-s', '--scope', multiple=True, help='Target asset keys to restrict the hunt (repeatable)')
@click.option('--scope-level', type=click.Choice(['normal', 'strict']), default='normal', show_default=True)
@click.option('--aggressiveness', type=click.Choice(['cautious', 'balanced', 'aggressive']),
              default='balanced', show_default=True)
@click.option('--internal', 'internal_hunt', is_flag=True, default=False,
              help='Require all target-network work to use one Aegis v2 endpoint')
@click.option('--endpoint', 'endpoint_id', default=None,
              help='Aegis v2 endpoint ID or unique hostname for an Internal Hunt')
@click.option('--confirm-endpoint', is_flag=True, default=False,
              help='Confirm endpoint-only execution without an interactive prompt')
def launch(sdk, prompt, expires, agent, scope, scope_level, aggressiveness,
           internal_hunt, endpoint_id, confirm_endpoint):
    """Launch a new hunt against the current account.

    Example usages:
        guard hunt launch --prompt "Find XSS vulnerabilities in web applications"
        guard hunt launch --prompt "Test API endpoints" --agent hannibal-webapp --expires 24
        guard hunt launch --prompt "Cloud misconfigs" --agent hannibal-cloud --scope "#asset#example.com#1.2.3.4"
        guard hunt launch --internal --endpoint <endpoint-id> --scope "#asset#internal#10.0.0.5" --prompt "Assess internal services"
    """
    endpoint = _internal_hunt_endpoint(
        sdk,
        endpoint_id,
        internal_hunt,
        agent,
        scope,
        confirm_endpoint,
    )
    if endpoint and not confirm_endpoint:
        endpoint_name = endpoint.hostname or endpoint.display_id
        online = 'online' if endpoint.is_online else 'offline'
        confirmed = click.confirm(
            f'Run all target-network work for {len(scope)} internal scope '
            f'item(s) through {endpoint_name} ({endpoint.display_id}, {online})? '
            'If unavailable, the hunt waits without Guard compute fallback',
            default=False,
        )
        if not confirmed:
            raise click.Abort()

    result = sdk.hunts.create(
        prompt=prompt,
        expires_hours=expires,
        agent=agent,
        scope=list(scope) if scope else None,
        scope_level=scope_level,
        aggressiveness=aggressiveness,
        endpoint_required=internal_hunt,
        endpoint_id=endpoint.display_id if endpoint else None,
        endpoint_confirmed=bool(endpoint),
    )
    print_json(result)


@hunt.command('list')
@cli_handler
@click.option('-s', '--status', type=click.Choice(['active', 'paused', 'completed', 'stopped', 'expired', 'errored']),
              default=None, help='Filter by hunt status')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@click.option('-p', '--page', type=click.Choice(['first', 'all']), default='first', show_default=True)
def list_hunts(sdk, status, details, page):
    """List hunts for the current account.

    Example usages:
        guard hunt list
        guard hunt list --status active --details
        guard hunt list --page all
    """
    render_list_results(sdk.hunts.list(status=status, pages=pagination_size(page)), details)


@hunt.command()
@cli_handler
@click.argument('uuid')
def status(sdk, uuid):
    """Show detailed status of a hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt status a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.get(uuid)
    if not result:
        click.secho(f'Hunt {uuid} not found.', fg='red', err=True)
        return
    fields = {
        'uuid': result.get('uuid', result.get('key', '').replace('#hunt#', '')),
        'status': result.get('status'),
        'agent': result.get('agent'),
        'prompt': result.get('prompt', '')[:120],
        'iterations': result.get('iterationCount', 0),
        'findings': result.get('findingsCount', 0),
        'created': result.get('created'),
        'expires': result.get('expiresAt'),
        'lastError': result.get('lastError', ''),
    }
    if result.get('endpointRequired'):
        fields.update({
            'endpointRequired': True,
            'endpointId': result.get('endpointId'),
            'currentWorkflowRunId': result.get('currentWorkflowRunId'),
        })
        try:
            endpoint_status = sdk.hunts.endpoint_execution_status(result)
        except Exception:
            fields['endpointExecution'] = [
                'Endpoint execution status is temporarily unavailable.'
            ]
        else:
            rendered_status = format_endpoint_execution_status(endpoint_status)
            if rendered_status:
                fields['endpointExecution'] = rendered_status.splitlines()
    print_json(fields)


@hunt.command()
@cli_handler
@click.argument('uuid')
def stop(sdk, uuid):
    """Stop a running hunt permanently.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt stop a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.stop(uuid)
    click.echo(f'Hunt {uuid} stopped.')
    print_json(result)


@hunt.command()
@cli_handler
@click.argument('uuid')
def pause(sdk, uuid):
    """Pause an active hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt pause a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.pause(uuid)
    click.echo(f'Hunt {uuid} paused.')
    print_json(result)


@hunt.command()
@cli_handler
@click.argument('uuid')
def resume(sdk, uuid):
    """Resume a paused hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt resume a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.resume(uuid)
    click.echo(f'Hunt {uuid} resumed.')
    print_json(result)


@hunt.command('delete')
@cli_handler
@click.argument('uuid')
@click.confirmation_option(prompt='This will delete the hunt and its artifacts. Findings are preserved. Continue?')
def delete_hunt(sdk, uuid):
    """Delete a hunt. Findings are preserved.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt delete a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    sdk.hunts.delete(uuid)
    click.echo(f'Hunt {uuid} deleted.')
