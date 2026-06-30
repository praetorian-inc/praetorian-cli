"""Hannibal hunt management — create, monitor, and control persistent hunting agents."""
import json
import time

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


STATUS_COLORS = {
    'active': 'green',
    'paused': 'yellow',
    'completed': 'cyan',
    'stopped': 'red',
    'expired': 'magenta',
    'errored': 'red',
}


def _format_hunt_line(h):
    """Format a single hunt for list display."""
    uuid = h.get('uuid', h.get('key', '?'))
    status = h.get('status', '?')
    color = STATUS_COLORS.get(status, 'white')
    prompt = (h.get('prompt', '') or '')[:60]
    if len(h.get('prompt', '') or '') > 60:
        prompt += '...'
    iterations = h.get('iterationCount', 0)
    findings = h.get('findingsCount', 0)
    return (
        f"{uuid}  "
        f"{click.style(status, fg=color, bold=True):>20s}  "
        f"iterations={iterations}  findings={findings}  "
        f"{prompt}"
    )


def _parse_duration(duration_str):
    """Parse a human-friendly duration like '24h', '12h', '72h' into hours."""
    duration_str = duration_str.strip().lower()
    if duration_str.endswith('h'):
        try:
            return int(duration_str[:-1])
        except ValueError:
            pass
    if duration_str.endswith('d'):
        try:
            return int(duration_str[:-1]) * 24
        except ValueError:
            pass
    try:
        return int(duration_str)
    except ValueError:
        error(f'Invalid duration: {duration_str}. Use e.g. "24h", "48h", "72h", or "3d".')


@chariot.group('hunt')
def hunt():
    """Manage Hannibal persistent hunting agents.

    \b
    Hannibal is Guard's autonomous offensive security agent. A hunt is a
    persistent, tenant-scoped agent instance that iterates: selecting targets,
    planning dispatches, running exploit agents, and reporting findings.

    \b
    Examples:
        guard hunt start "Find SQL injection in web apps" --duration 24h
        guard hunt list
        guard hunt show <uuid>
        guard hunt pause <uuid>
        guard hunt resume <uuid>
        guard hunt stop <uuid>
    """
    pass


@hunt.command('start')
@cli_handler
@click.argument('prompt')
@click.option('--duration', default='24h', help='Hunt duration (e.g. 12h, 24h, 48h, 72h, 3d). Max 72h.', show_default=True)
@click.option('--scope', multiple=True, help='Scope to specific assets (e.g. "#asset#example.com"). Repeatable.')
@click.option('--finish-criteria', default=None, help='Optional criteria for the agent to self-complete.')
@click.option('--agent', default=None, help='Agent name (default: hannibal).')
@click.option('--allowed-tools', multiple=True, help='Restrict to specific tools. Repeatable.')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON response.')
def start(sdk, prompt, duration, scope, finish_criteria, agent, allowed_tools, json_out):
    """Launch a new Hannibal hunt.

    \b
    PROMPT is the hunt mandate — what Hannibal should look for.

    \b
    Examples:
        guard hunt start "Find critical web vulnerabilities"
        guard hunt start "Test OAuth flows on api.example.com" --scope "#asset#api.example.com"
        guard hunt start "Hunt for RCE in Java services" --duration 48h
        guard hunt start "Find SQLi" --finish-criteria "At least 3 confirmed SQL injection findings"
    """
    from datetime import datetime, timezone, timedelta

    hours = _parse_duration(duration)
    if hours > 72:
        error('Maximum hunt duration is 72 hours.')
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')

    body = {
        'prompt': prompt,
        'expiresAt': expires_at,
    }
    if scope:
        body['scope'] = list(scope)
    if finish_criteria:
        body['finishCriteria'] = finish_criteria
    if agent:
        body['agent'] = agent
    if allowed_tools:
        body['allowedTools'] = list(allowed_tools)

    result = sdk.post('hunt', body)

    if json_out:
        print_json(result)
        return

    uuid = result.get('uuid', '?')
    status = result.get('status', '?')
    click.echo(click.style('Hannibal is at the gates!', fg='red', bold=True))
    click.echo()
    click.echo(f'  Hunt:     {uuid}')
    click.echo(f'  Status:   {click.style(status, fg="green", bold=True)}')
    click.echo(f'  Expires:  {expires_at}')
    click.echo(f'  Mandate:  {prompt}')
    if scope:
        click.echo(f'  Scope:    {", ".join(scope)}')
    click.echo()
    click.echo(f'Track progress: guard hunt show {uuid}')
    click.echo(f'Watch live:     guard hunt watch {uuid}')


@hunt.command('list')
@cli_handler
@click.option('--status', 'filter_status', default=None,
              type=click.Choice(['active', 'paused', 'completed', 'stopped', 'expired', 'errored']),
              help='Filter by hunt status.')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON.')
def list_hunts(sdk, filter_status, json_out):
    """List all hunts for the current account.

    \b
    Examples:
        guard hunt list
        guard hunt list --status active
        guard hunt list --json-output
    """
    resp = sdk.my({'key': '#hunt'})
    hunts = resp.get('hunts', resp.get('data', []))

    if not isinstance(hunts, list):
        for key in resp:
            if isinstance(resp[key], list):
                hunts = resp[key]
                break
        else:
            hunts = []

    if filter_status:
        hunts = [h for h in hunts if h.get('status') == filter_status]

    if json_out:
        print_json({'hunts': hunts, 'count': len(hunts)})
        return

    if not hunts:
        click.echo('No hunts found.' + (f' (filter: {filter_status})' if filter_status else ''))
        return

    click.echo(click.style(f'{len(hunts)} hunt(s)', bold=True))
    click.echo(click.style('─' * 80, dim=True))
    for h in hunts:
        click.echo(_format_hunt_line(h))


@hunt.command('show')
@cli_handler
@click.argument('uuid')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON.')
def show(sdk, uuid, json_out):
    """Show details of a specific hunt.

    \b
    UUID is the hunt identifier.

    \b
    Examples:
        guard hunt show 550e8400-e29b-41d4-a716-446655440000
    """
    resp = sdk.my({'key': f'#hunt#{uuid}'})
    hunts = resp.get('hunts', resp.get('data', []))

    if not isinstance(hunts, list):
        for key in resp:
            if isinstance(resp[key], list):
                hunts = resp[key]
                break
        else:
            hunts = []

    if not hunts:
        error(f'Hunt {uuid} not found.')

    h = hunts[0]

    if json_out:
        print_json(h)
        return

    status = h.get('status', '?')
    color = STATUS_COLORS.get(status, 'white')

    click.echo(click.style('Hunt Details', bold=True))
    click.echo(click.style('─' * 60, dim=True))
    click.echo(f'  UUID:           {h.get("uuid", "?")}')
    click.echo(f'  Status:         {click.style(status, fg=color, bold=True)}')
    click.echo(f'  Created:        {h.get("created", "?")}')
    click.echo(f'  Created By:     {h.get("createdBy", "?")}')
    click.echo(f'  Expires:        {h.get("expiresAt", "?")}')
    click.echo(f'  Agent:          {h.get("agent", "hannibal")}')
    click.echo(f'  Iterations:     {h.get("iterationCount", 0)}')
    click.echo(f'  Findings:       {h.get("findingsCount", 0)}')
    click.echo(f'  Last Started:   {h.get("lastStartedAt", "—")}')
    click.echo(f'  Last Completed: {h.get("lastCompletedAt", "—")}')

    prompt = h.get('prompt', '')
    if prompt:
        click.echo(f'  Mandate:')
        for line in prompt.split('\n'):
            click.echo(f'    {line}')

    scope = h.get('scope', [])
    if scope:
        click.echo(f'  Scope:')
        for s in scope:
            click.echo(f'    {s}')

    finish = h.get('finishCriteria', '')
    if finish:
        click.echo(f'  Finish Criteria: {finish}')

    last_error = h.get('lastError', '')
    if last_error:
        click.echo(f'  Last Error:     {click.style(last_error, fg="red")}')


@hunt.command('pause')
@cli_handler
@click.argument('uuid')
def pause(sdk, uuid):
    """Pause an active hunt. The hunt can be resumed later.

    \b
    Examples:
        guard hunt pause 550e8400-e29b-41d4-a716-446655440000
    """
    result = sdk.put(f'hunt/{uuid}', {'status': 'paused'})
    status = result.get('status', '?')
    click.echo(f'Hunt {uuid}: {click.style(status, fg="yellow", bold=True)}')


@hunt.command('resume')
@cli_handler
@click.argument('uuid')
def resume(sdk, uuid):
    """Resume a paused hunt.

    \b
    Examples:
        guard hunt resume 550e8400-e29b-41d4-a716-446655440000
    """
    result = sdk.put(f'hunt/{uuid}', {'status': 'active'})
    status = result.get('status', '?')
    click.echo(f'Hunt {uuid}: {click.style(status, fg="green", bold=True)}')


@hunt.command('stop')
@cli_handler
@click.argument('uuid')
def stop(sdk, uuid):
    """Stop a hunt permanently. Cannot be resumed.

    \b
    Examples:
        guard hunt stop 550e8400-e29b-41d4-a716-446655440000
    """
    result = sdk.put(f'hunt/{uuid}', {'status': 'stopped'})
    status = result.get('status', '?')
    click.echo(f'Hunt {uuid}: {click.style(status, fg="red", bold=True)}')


@hunt.command('delete')
@cli_handler
@click.argument('uuid')
@click.confirmation_option(prompt='Delete this hunt? Findings will be preserved.')
def delete(sdk, uuid):
    """Delete a hunt record. Findings (risks) are preserved.

    \b
    Examples:
        guard hunt delete 550e8400-e29b-41d4-a716-446655440000
    """
    sdk.delete(f'hunt/{uuid}', {}, {'uuid': uuid})
    click.echo(f'Hunt {uuid}: {click.style("deleted", fg="red")}')


@hunt.command('cost')
@cli_handler
@click.argument('uuid')
def cost(sdk, uuid):
    """Show AI cost breakdown for a hunt.

    \b
    Examples:
        guard hunt cost 550e8400-e29b-41d4-a716-446655440000
    """
    result = sdk.get(f'hunt/{uuid}/cost')
    print_json(result)


@hunt.command('active')
@cli_handler
def active(sdk):
    """Quick status check on all running hunts. Use to check background hunts.

    \b
    Examples:
        guard hunt active
    """
    resp = sdk.my({'key': '#hunt'})
    hunts = resp.get('hunts', resp.get('data', []))
    if not isinstance(hunts, list):
        for key in resp:
            if isinstance(resp[key], list):
                hunts = resp[key]
                break
        else:
            hunts = []

    active_hunts = [h for h in hunts if h.get('status') in ('active', 'paused')]
    if not active_hunts:
        click.echo('No active or paused hunts.')
        click.echo('Start one: guard hunt start "Find vulnerabilities"')
        return

    click.echo(click.style(f'{len(active_hunts)} running hunt(s)', bold=True))
    click.echo(click.style('─' * 80, dim=True))
    for h in active_hunts:
        uuid = h.get('uuid', '?')
        status = h.get('status', '?')
        color = STATUS_COLORS.get(status, 'white')
        prompt = (h.get('prompt', '') or '')[:50]
        iterations = h.get('iterationCount', 0)
        findings = h.get('findingsCount', 0)
        click.echo(
            f"  {uuid}  "
            f"{click.style(status, fg=color, bold=True)}  "
            f"i={iterations} f={findings}  "
            f"{prompt}"
        )
    click.echo()
    click.echo(click.style('Reconnect:', dim=True) + f' guard hunt interactive <uuid>')
    click.echo(click.style('Watch:', dim=True) + f'     guard hunt watch <uuid>')


@hunt.command('interactive')
@cli_handler
@click.argument('uuid_or_prompt', required=False, default=None)
@click.option('--duration', default='24h', help='Hunt duration when starting new (e.g. 24h, 48h).', show_default=True)
@click.option('--scope', multiple=True, help='Scope to specific assets. Repeatable.')
def interactive(sdk, uuid_or_prompt, duration, scope):
    """Launch the interactive Hannibal TUI.

    \b
    Opens a Claude Code-style terminal interface for managing hunts.
    Without arguments, opens the TUI ready for commands. With a UUID,
    connects to an existing hunt. With text, starts a new hunt.

    \b
    Examples:
        guard hunt interactive
        guard hunt interactive 550e8400-e29b-41d4-a716-446655440000
        guard hunt interactive "Find SQL injection vulnerabilities"
    """
    from praetorian_cli.ui.hunt.app import run_hunt_tui

    hunt_uuid = None
    start_prompt = None

    if uuid_or_prompt:
        # Heuristic: UUIDs are 36 chars with dashes
        if len(uuid_or_prompt) == 36 and uuid_or_prompt.count('-') == 4:
            hunt_uuid = uuid_or_prompt
        else:
            start_prompt = uuid_or_prompt

    run_hunt_tui(sdk, hunt_uuid=hunt_uuid, start_prompt=start_prompt,
                 start_duration=duration, start_scope=list(scope) if scope else None)


@hunt.command('watch')
@cli_handler
@click.argument('uuid')
@click.option('--interval', default=10, type=int, help='Poll interval in seconds.', show_default=True)
def watch(sdk, uuid, interval):
    """Watch a hunt's progress in real-time. Polls for status updates.

    \b
    Press Ctrl+C to stop watching (the hunt continues running).

    \b
    Examples:
        guard hunt watch 550e8400-e29b-41d4-a716-446655440000
        guard hunt watch 550e8400-e29b-41d4-a716-446655440000 --interval 30
    """
    click.echo(click.style(f'Watching hunt {uuid}', bold=True) + f'  (Ctrl+C to stop watching)')
    click.echo(click.style('─' * 60, dim=True))

    prev_iterations = -1
    prev_findings = -1

    try:
        while True:
            resp = sdk.my({'key': f'#hunt#{uuid}'})
            hunts = resp.get('hunts', resp.get('data', []))

            if not isinstance(hunts, list):
                for key in resp:
                    if isinstance(resp[key], list):
                        hunts = resp[key]
                        break
                else:
                    hunts = []

            if not hunts:
                click.echo(click.style(f'Hunt {uuid} not found.', fg='red'))
                return

            h = hunts[0]
            status = h.get('status', '?')
            color = STATUS_COLORS.get(status, 'white')
            iterations = h.get('iterationCount', 0)
            findings = h.get('findingsCount', 0)

            if iterations != prev_iterations or findings != prev_findings:
                ts = time.strftime('%H:%M:%S')
                click.echo(
                    f'[{ts}]  '
                    f'{click.style(status, fg=color, bold=True):>20s}  '
                    f'iterations={iterations}  findings={findings}'
                )
                prev_iterations = iterations
                prev_findings = findings

            if status in ('completed', 'stopped', 'expired', 'errored'):
                click.echo()
                click.echo(click.style(f'Hunt {status}.', fg=color, bold=True))
                last_error = h.get('lastError', '')
                if last_error:
                    click.echo(click.style(f'Last error: {last_error}', fg='red'))
                return

            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo()
        click.echo('Stopped watching. The hunt continues running.')
