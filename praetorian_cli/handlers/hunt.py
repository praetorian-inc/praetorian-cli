import time

import click
from rich.console import Console

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, render_list_results, pagination_size
from praetorian_cli.sdk.model.aegis import is_v2_agent
from praetorian_cli.ui.conversation.endpoint_status import (
    format_endpoint_execution_status,
)
from praetorian_cli.ui.entity_resolver import resolve_entity_reference
from praetorian_cli.ui.entity_selector import select_entity_keys
from praetorian_cli.ui.hunt_chat import (
    build_hunt_chat,
    select_hunt_conversation,
)
from praetorian_cli.ui.hunt_data import (
    build_hunt_findings,
    build_hunt_log,
    build_hunt_memory,
    build_hunt_memory_item,
    filter_hunt_findings,
)
from praetorian_cli.ui.hunt_defaults import (
    DEFAULT_FINISH_CRITERIA,
    DEFAULT_HUNT_DURATION_HOURS,
    DEFAULT_HUNT_MANDATES,
)
from praetorian_cli.ui.hunt_launch import (
    configure_hunt_launch,
    hunt_surface_label,
    supports_fullscreen_wizard,
)
from praetorian_cli.ui.hunt_workflows import browse_hunt_workflows


SURFACE_TO_AGENT = {
    'external': 'hannibal',
    'internal': 'hannibal',
    'cloud': 'hannibal-cloud',
    'webapp': 'hannibal-webapp',
    'llm': 'hannibal-llm',
}
AGENT_TO_SURFACE = {
    agent: surface
    for surface, agent in SURFACE_TO_AGENT.items()
    if surface != 'internal'
}


@chariot.group()
def hunt():
    """Manage Hannibal hunts — launch, monitor, and control automated vulnerability discovery."""
    pass


def _require_hunt(sdk, hunt_id):
    hunt_record = sdk.hunts.get(hunt_id)
    if not hunt_record:
        raise click.ClickException(f'Hunt {hunt_id} not found')
    return hunt_record


def _hunt_surface(agent, internal_hunt):
    if internal_hunt:
        return 'internal'
    return AGENT_TO_SURFACE[agent]


def _hunt_scope_type(surface):
    return 'webapplication' if surface in ('webapp', 'llm') else 'asset'


def _select_hunt_scope(sdk, surface, console):
    agent = SURFACE_TO_AGENT[surface]
    internal_hunt = surface == 'internal'
    candidates, next_scope_page = sdk.assets.list_hunt_scope(
        agent=agent,
        internal=internal_hunt,
        pages=1,
    )
    return select_entity_keys(
        console,
        candidates,
        title=f'Select {hunt_surface_label(surface)} Hunt targets',
        search_entities=lambda query, page: sdk.assets.list_hunt_scope(
            agent=agent,
            internal=internal_hunt,
            search=query,
            page=int(page or 0),
            pages=1,
        ),
        next_offset=next_scope_page,
    )


def _record_value(record, *names):
    for name in names:
        if isinstance(record, dict):
            value = record.get(name)
        else:
            value = getattr(record, name, None)
        if value is not None:
            return value
    return None


def _hunt_credentials(sdk, endpoint_id):
    credentials_api = getattr(sdk, 'credentials', None)
    if credentials_api is None:
        return []
    try:
        credentials, _ = credentials_api.list(pages=1)
    except Exception:
        return []

    supported = []
    for credential in credentials:
        credential_type = _record_value(
            credential,
            'type',
            'credentialType',
        )
        if credential_type == 'web-auth':
            supported.append(credential)
            continue
        if credential_type != 'active-directory':
            continue
        endpoint_ids = _record_value(
            credential,
            'endpointIds',
            'endpoint_ids',
        ) or []
        account_key = _record_value(
            credential,
            'accountKey',
            'account_key',
        )
        if endpoint_id in endpoint_ids or (
            not endpoint_ids and account_key == endpoint_id
        ):
            supported.append(credential)
    return supported


def _internal_hunt_endpoint(
    sdk,
    endpoint_id,
    internal_hunt,
    agent,
    scope,
    confirm_endpoint,
    allow_prompt=True,
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

    if not allow_prompt:
        raise click.UsageError(
            '--endpoint is required for an Internal Hunt in non-interactive mode'
        )

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
@click.option('-p', '--prompt', default=None,
              help='The hunt objective / central mandate (surface default when omitted)')
@click.option('-e', '--expires', type=click.IntRange(1, 72),
              default=DEFAULT_HUNT_DURATION_HOURS, show_default=True,
              help='Hours until the hunt expires (1-72)')
@click.option('-a', '--agent', type=click.Choice(['hannibal', 'hannibal-cloud', 'hannibal-webapp', 'hannibal-llm']),
              default='hannibal', show_default=True, help='Agent type')
@click.option('-s', '--scope', multiple=True,
              help='Target key, hostname, IP, URL, or friendly name (repeatable)')
@click.option('--scope-mode', type=click.Choice(['all', 'specific']), default=None,
              help='Hunt all infrastructure or require specific targets')
@click.option('--select-scope', is_flag=True,
              help='Search and select Hunt targets interactively')
@click.option('--scope-level', type=click.Choice(['normal', 'strict']), default='normal', show_default=True)
@click.option('--aggressiveness', type=click.Choice(['cautious', 'balanced', 'aggressive']),
              default='balanced', show_default=True)
@click.option('--finish-criteria', default=DEFAULT_FINISH_CRITERIA,
              help='Conditions that allow the Hunt to finish early')
@click.option('--guardrails', default='',
              help='Additional tighten-only safety restrictions')
@click.option('--custom-tag', default='',
              help='Tag assigned to findings created by this Hunt')
@click.option('--model-tier', type=click.Choice(['experimental']), default=None,
              help='Privileged model tier override')
@click.option('--credential', 'credential_ids', multiple=True,
              help='Run-scoped credential ID or key (repeatable, one per type)')
@click.option('--internal', 'internal_hunt', is_flag=True, default=False,
              help='Require all target-network work to use one Aegis v2 endpoint')
@click.option('--endpoint', 'endpoint_id', default=None,
              help='Aegis v2 endpoint ID or unique hostname for an Internal Hunt')
@click.option('--confirm-endpoint', is_flag=True, default=False,
              help='Confirm endpoint-only execution without an interactive prompt')
@click.option('-y', '--yes', is_flag=True, default=False,
              help='Use flag/default values without prompts or fullscreen UI')
def launch(sdk, prompt, expires, agent, scope, scope_mode, select_scope,
           scope_level, aggressiveness, finish_criteria, guardrails,
           custom_tag, model_tier, credential_ids, internal_hunt, endpoint_id,
           confirm_endpoint, yes):
    """Launch a new Hunt, using the all-surface wizard in an interactive TTY.

    Example usages:
        guard hunt launch
        guard hunt launch --yes --prompt "Find exploitable external paths"
        guard hunt launch --agent hannibal-webapp --select-scope
        guard hunt launch --agent hannibal-cloud --scope "#asset#aws#123456789012"
        guard hunt launch --internal --endpoint <endpoint-id> --scope "#asset#internal#10.0.0.5"
    """
    if internal_hunt and agent != 'hannibal':
        raise click.UsageError(
            '--internal requires the hannibal infrastructure agent'
        )
    if yes and select_scope:
        raise click.UsageError('--select-scope cannot be combined with --yes')

    initial_surface = _hunt_surface(agent, internal_hunt)
    if scope_mode == 'all' and (
        scope or select_scope or internal_hunt or agent != 'hannibal'
    ):
        raise click.UsageError(
            '--scope-mode all is only valid for an unscoped External Hunt'
        )
    selected_scope_mode = scope_mode or (
        'specific'
        if scope or select_scope or internal_hunt or agent != 'hannibal'
        else 'all'
    )
    interactive_terminal = supports_fullscreen_wizard()
    if select_scope and not interactive_terminal:
        raise click.UsageError('--select-scope requires an interactive TTY')
    console = Console()
    scopes = [
        resolve_entity_reference(
            sdk,
            value,
            _hunt_scope_type(initial_surface),
            interactive=interactive_terminal and not yes,
            console=console,
        )
        for value in scope
    ]

    should_select_scope = selected_scope_mode == 'specific' and (
        select_scope or (not scopes and interactive_terminal and not yes)
    )
    if should_select_scope:
        selected_scopes = _select_hunt_scope(sdk, initial_surface, console)
        if not selected_scopes:
            raise click.Abort()
        scopes = list(dict.fromkeys([*scopes, *selected_scopes]))

    endpoint = None
    credential_options = []
    if initial_surface == 'internal' and scopes:
        endpoint = _internal_hunt_endpoint(
            sdk,
            endpoint_id,
            True,
            'hannibal',
            scopes,
            confirm_endpoint or yes,
            allow_prompt=interactive_terminal and not yes,
        )
        if interactive_terminal and not yes:
            credential_options = _hunt_credentials(sdk, endpoint.display_id)

    launch_config = {
        'surface': initial_surface,
        'scope_mode': selected_scope_mode,
        'scope': list(scopes),
        'prompt': prompt or DEFAULT_HUNT_MANDATES[initial_surface],
        'scope_level': scope_level,
        'aggressiveness': aggressiveness,
        'guardrails': guardrails,
        'finish_criteria': finish_criteria,
        'expires': expires,
        'custom_tag': custom_tag,
        'model_tier': model_tier,
        'credential_ids': list(credential_ids),
    }
    used_wizard = False
    if not yes:
        endpoint_description = 'Not required'
        if initial_surface == 'internal':
            if endpoint is None:
                endpoint_description = 'Select after target review'
            else:
                endpoint_name = endpoint.hostname or endpoint.display_id
                endpoint_state = 'online' if endpoint.is_online else 'offline'
                endpoint_description = (
                    f'{endpoint_name} ({endpoint.display_id}, {endpoint_state})'
                )
        launch_config, used_wizard = configure_hunt_launch(
            console,
            launch_config,
            scopes,
            endpoint_description,
            credential_options,
        )
        if used_wizard and launch_config is None:
            raise click.Abort()

    surface = launch_config.get('surface', initial_surface)
    selected_scope_mode = launch_config.get(
        'scope_mode',
        selected_scope_mode,
    )
    if selected_scope_mode == 'all':
        surface = 'external'
        scopes = []
    else:
        scopes = list(launch_config.get('scope') or [])
    agent = SURFACE_TO_AGENT[surface]
    internal_hunt = surface == 'internal'
    prompt = (
        str(launch_config.get('prompt') or '').strip()
        or DEFAULT_HUNT_MANDATES[surface]
    )
    expires = launch_config.get('expires', expires)
    scope_level = launch_config.get('scope_level', scope_level)
    aggressiveness = launch_config.get('aggressiveness', aggressiveness)
    finish_criteria = (
        str(launch_config.get('finish_criteria') or '').strip()
        or DEFAULT_FINISH_CRITERIA
    )
    guardrails = str(launch_config.get('guardrails') or '').strip()
    custom_tag = str(launch_config.get('custom_tag') or '').strip()
    model_tier = launch_config.get('model_tier', model_tier)
    credential_ids = list(
        launch_config.get('credential_ids', credential_ids) or []
    )

    can_prompt = (interactive_terminal or used_wizard) and not yes
    if selected_scope_mode == 'specific' and not scopes:
        if not can_prompt:
            raise click.UsageError(
                'Specific Hunts require at least one --scope or --select-scope'
            )
        selected_scopes = _select_hunt_scope(sdk, surface, console)
        if not selected_scopes:
            raise click.Abort()
        scopes = selected_scopes

    if credential_ids and not internal_hunt:
        raise click.UsageError('--credential requires --internal')

    if used_wizard and initial_surface == 'internal' and not internal_hunt:
        endpoint_id = None
        confirm_endpoint = False
    if surface != initial_surface:
        endpoint = None
    if endpoint is None or not internal_hunt:
        endpoint = _internal_hunt_endpoint(
            sdk,
            endpoint_id,
            internal_hunt,
            agent,
            scopes,
            (confirm_endpoint or yes) if internal_hunt else confirm_endpoint,
            allow_prompt=can_prompt,
        )

    endpoint_confirmed = confirm_endpoint or yes
    if endpoint and not endpoint_confirmed:
        if not can_prompt:
            raise click.UsageError(
                '--confirm-endpoint or --yes is required for an Internal Hunt '
                'in non-interactive mode'
            )
        endpoint_name = endpoint.hostname or endpoint.display_id
        online = 'online' if endpoint.is_online else 'offline'
        confirmed = click.confirm(
            f'Run all target-network work for {len(scopes)} internal scope '
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
        scope=scopes or None,
        scope_level=scope_level,
        aggressiveness=aggressiveness,
        finish_criteria=finish_criteria,
        user_guardrails=guardrails,
        custom_tag=custom_tag,
        model_tier_override=model_tier,
        credential_ids=credential_ids or None,
        endpoint_required=internal_hunt,
        endpoint_id=endpoint.display_id if endpoint else None,
        endpoint_confirmed=bool(endpoint),
    )
    print_json(result)


@hunt.command()
@cli_handler
@click.argument('uuid')
@click.option('--status', default=None, help='Risk status code or label')
@click.option(
    '--severity',
    type=click.Choice(['critical', 'high', 'medium', 'low', 'info', 'exposure']),
    default=None,
)
@click.option('--details', is_flag=True, help='Show finding details')
@click.option(
    '--evidence',
    type=click.Choice(['off', 'basic', 'full']),
    default='off',
    show_default=True,
)
@click.option('--page', type=click.Choice(['first', 'all']), default='first', show_default=True)
def findings(sdk, uuid, status, severity, details, evidence, page):
    """List vulnerabilities reported by a Hunt."""
    _require_hunt(sdk, uuid)
    records, _ = sdk.hunts.list_findings(
        uuid,
        pages=pagination_size(page),
    )
    records = filter_hunt_findings(records, status=status, severity=severity)
    if details or evidence != 'off':
        records = [
            sdk.risks.get(
                record.get('key'),
                details=True,
                evidence=evidence,
            )
            for record in records
            if record.get('key')
        ]
    Console().print(
        build_hunt_findings(
            records,
            show_details=details or evidence != 'off',
        )
    )


@hunt.command()
@cli_handler
@click.argument('uuid')
@click.option('--item', help='Memory item title to read or modify')
@click.option('--content', default=None, help='Replacement memory content')
@click.option('--delete', 'delete_item', is_flag=True, help='Delete the selected item')
@click.option('-y', '--yes', is_flag=True, help='Skip delete confirmation')
def memory(sdk, uuid, item, content, delete_item, yes):
    """List, read, edit, or delete Hunt memory."""
    _require_hunt(sdk, uuid)
    if content is not None and delete_item:
        raise click.UsageError('--content and --delete cannot be combined')
    if (content is not None or delete_item) and not item:
        raise click.UsageError('--item is required when modifying memory')

    if delete_item:
        if not yes and not click.confirm(f'Delete Hunt memory item {item!r}?'):
            raise click.Abort()
        sdk.hunts.delete_memory(uuid, item)
        click.secho(f'Deleted Hunt memory item {item}.', fg='green')
        return
    if content is not None:
        sdk.hunts.save_memory(uuid, item, content)
        click.secho(f'Saved Hunt memory item {item}.', fg='green')
        return
    if item:
        Console().print(
            build_hunt_memory_item(item, sdk.hunts.get_memory(uuid, item))
        )
        return

    items, _ = sdk.hunts.list_memory(uuid)
    Console().print(build_hunt_memory(items))


@hunt.command()
@cli_handler
@click.argument('uuid')
@click.option('--follow', is_flag=True, help='Continue printing log updates')
@click.option('--interval', type=click.FloatRange(min=1), default=5.0, show_default=True)
def log(sdk, uuid, follow, interval):
    """Show the finalized-iteration Hunt log."""
    _require_hunt(sdk, uuid)
    console = Console()
    content = sdk.hunts.get_log(uuid)
    console.print(build_hunt_log(content))
    if not follow:
        return

    try:
        while True:
            time.sleep(interval)
            latest = sdk.hunts.get_log(uuid)
            if latest == content:
                continue
            update = latest[len(content):] if latest.startswith(content) else latest
            content = latest
            console.print(build_hunt_log(update))
    except KeyboardInterrupt:
        click.echo('\nStopped following Hunt log.')


@hunt.command()
@cli_handler
@click.argument('uuid')
@click.option('--conversation', 'conversation_id', help='Conversation ID or unique prefix to view')
@click.option('-m', '--message', help='Queue guidance for the active Hunt iteration')
def chat(sdk, uuid, conversation_id, message):
    """View Hunt chat or send guidance to the active iteration."""
    _require_hunt(sdk, uuid)
    try:
        if message is not None and not message.strip():
            raise ValueError('guidance message is required')
        conversations, _ = sdk.hunts.list_conversations(uuid)
        selected = select_hunt_conversation(
            conversations,
            requested_id=conversation_id,
            require_active=message is not None,
        )
        selected_id = selected.get('uuid') or selected.get('id')
        if message is not None:
            sdk.conversations.send_message(selected_id, message)
        transcript = sdk.conversations.get(selected_id)
    except Exception as exc:
        raise click.ClickException(f'Unable to open Hunt chat: {exc}') from exc

    Console().print(build_hunt_chat(conversations, selected, transcript))
    if message is not None:
        click.secho('Guidance queued for the running Hunt iteration.', fg='green')


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
@click.option('--workflows', is_flag=True, help='Show workflow iterations and steps')
def status(sdk, uuid, workflows):
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
        'credentialIds': result.get('credentialIds', []),
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
    if workflows:
        try:
            runs, _ = sdk.hunts.list_workflow_runs(uuid)
        except Exception as exc:
            raise click.ClickException(
                f'Unable to load Hunt workflows: {exc}'
            ) from exc
        click.echo()
        browse_hunt_workflows(Console(), runs)


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
