"""CritFinder — adversarial vulnerability research pipeline."""
import click
import time
import json

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error


# Progress line color coding
PHASE_COLORS = {
    'critfinder': 'white',
    'scanner': 'cyan',
    'gatekeeper': 'yellow',
    'exploiter': 'green',
}

VERDICT_COLORS = {
    'APPROVED': 'yellow',
    'REJECTED': 'red',
    'NEEDS REWORK': 'magenta',
    'CONFIRMED': 'green',
    'DENIED': 'red',
}


def _colorize_progress(line):
    """Apply color coding to structured progress lines."""
    for phase, color in PHASE_COLORS.items():
        if line.startswith(f'[{phase}]'):
            # Check for verdict keywords
            for verdict, vcolor in VERDICT_COLORS.items():
                if verdict in line:
                    parts = line.split(verdict, 1)
                    return click.style(parts[0], fg=color) + click.style(verdict, fg=vcolor, bold=True) + click.style(parts[1] if len(parts) > 1 else '', fg=color)
            return click.style(line, fg=color)
    # Escalation alerts
    if 'ESCALAT' in line.upper() or 'STOP' in line.upper():
        return click.style(line, fg='red', bold=True)
    return line


def _build_research_message(target, depth, novel, research_mode):
    """Build the research request message for the coordinator agent."""
    parts = ['Run CritFinder research pipeline.']

    if research_mode == 'knowledge':
        parts.append('Mode: knowledge research.')
        if target:
            parts.append(f'Research topic: {target}')
    else:
        if novel:
            parts.append('Mode: novel — hunt for 0days and new variants.')
        else:
            parts.append('Mode: offensive — find critical vulnerabilities.')

        if target:
            parts.append(f'Scope: {target}')
        else:
            parts.append('Scope: full engagement — auto-select most promising attack surface.')

    if depth > 1:
        parts.append(f'Depth: {depth} cycles.')

    return ' '.join(parts)


def _stream_research(sdk, message, agent='research-coordinator'):
    """Send a message to the research-coordinator agent and stream progress."""
    try:
        result = sdk.agents.send(message, agent=agent)
        conversation_id = result.get('conversation_id') or result.get('id', '')

        if not conversation_id:
            # Direct response (no streaming)
            response = result.get('response', '')
            for line in response.split('\n'):
                click.echo(_colorize_progress(line))
            return

        # Poll for streaming responses
        seen_length = 0
        max_wait = 1800  # 30 min max
        start = time.time()

        while time.time() - start < max_wait:
            status = sdk.agents.poll(conversation_id)
            response = status.get('response', '')

            if len(response) > seen_length:
                new_content = response[seen_length:]
                for line in new_content.split('\n'):
                    if line.strip():
                        click.echo(_colorize_progress(line))
                seen_length = len(response)

            state = status.get('status', '')
            if state in ('complete', 'completed', 'error', 'failed'):
                if len(response) > seen_length:
                    for line in response[seen_length:].split('\n'):
                        if line.strip():
                            click.echo(_colorize_progress(line))
                if state in ('error', 'failed'):
                    error_msg = status.get('error', 'Research pipeline failed')
                    click.echo(click.style(f'\nError: {error_msg}', fg='red'), err=True)
                return

            time.sleep(2)

        click.echo(click.style('\nTimed out waiting for research pipeline (30 min).', fg='red'), err=True)

    except Exception as e:
        error(f'CritFinder error: {e}')


@chariot.command('critfinder')
@cli_handler
@click.argument('target', required=False, default=None)
@click.option('--depth', default=1, type=int, help='Pipeline cycles (1=single pass, 2-3=iterative)')
@click.option('--novel', is_flag=True, default=False, help='Hunt for 0days and new variants')
@click.option('--mode', 'research_mode', type=click.Choice(['offensive', 'knowledge']), default='offensive', help='Research mode')
def critfinder(sdk, target, depth, novel, research_mode):
    """Hunt for critical vulnerabilities in the current engagement.

    Runs the CritFinder adversarial research pipeline: SCANNER generates
    vulnerability hypotheses, GATEKEEPER filters weak findings, EXPLOITER
    validates and produces proof-of-concept exploits.

    \b
    Auto-selects the most promising attack surface if no target specified.
    Streams progress in real-time.

    \b
    Examples:
        guard critfinder                          # full engagement scan
        guard critfinder k8s.client.com           # scoped to target
        guard critfinder --depth 3                # iterative deep hunt
        guard critfinder --novel                  # 0day hunting mode
        guard critfinder --mode knowledge CVE-2024-1234
    """
    message = _build_research_message(target, depth, novel, research_mode)

    click.echo(click.style('CritFinder', bold=True) + ' — Adversarial Vulnerability Research Pipeline')
    click.echo(click.style('─' * 60, dim=True))
    if target:
        click.echo(f'Target: {target}')
    else:
        click.echo('Target: full engagement (auto-select)')
    click.echo(f'Mode: {"novel" if novel else research_mode}')
    click.echo(f'Depth: {depth} cycle{"s" if depth > 1 else ""}')
    click.echo(click.style('─' * 60, dim=True))
    click.echo()

    _stream_research(sdk, message)
