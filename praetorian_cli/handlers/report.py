import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


RISK_STATUS_COLORS = {
    'TH': ('TRIAGE HIGH', 'red'),
    'TM': ('TRIAGE MEDIUM', 'yellow'),
    'TL': ('TRIAGE LOW', 'cyan'),
    'TI': ('TRIAGE INFO', 'dim'),
    'OH': ('OPEN HIGH', 'red'),
    'OM': ('OPEN MEDIUM', 'yellow'),
    'OL': ('OPEN LOW', 'cyan'),
    'OI': ('OPEN INFO', 'dim'),
    'DH': ('DEMO HIGH', 'red'),
    'DM': ('DEMO MEDIUM', 'yellow'),
    'DL': ('DEMO LOW', 'cyan'),
    'DI': ('DEMO INFO', 'dim'),
    'DLO': ('DEMO (LOGGED OUT)', 'yellow'),
    'DCD': ('DEMO (CONFIRMED)', 'green'),
    'RH': ('RESOLVED HIGH', 'green'),
    'RM': ('RESOLVED MEDIUM', 'green'),
    'RL': ('RESOLVED LOW', 'green'),
    'RI': ('RESOLVED INFO', 'green'),
    'AH': ('ACCEPTED HIGH', 'magenta'),
    'AM': ('ACCEPTED MEDIUM', 'magenta'),
    'AL': ('ACCEPTED LOW', 'magenta'),
    'AI': ('ACCEPTED INFO', 'magenta'),
    'FP': ('FALSE POSITIVE', 'dim'),
}

PRIORITY_LABELS = {
    10: ('CRITICAL', 'red'),
    20: ('HIGH', 'red'),
    30: ('MEDIUM', 'yellow'),
    40: ('LOW', 'cyan'),
    50: ('INFO', 'dim'),
}


def _get_severity(risk):
    """Derive severity from priority field or status code."""
    priority = risk.get('priority', 0)
    if priority in PRIORITY_LABELS:
        return PRIORITY_LABELS[priority]
    status = risk.get('status', '')
    if len(status) >= 2:
        sev_char = status[-1]
        sev_map = {'H': ('HIGH', 'red'), 'M': ('MEDIUM', 'yellow'),
                   'L': ('LOW', 'cyan'), 'I': ('INFO', 'dim')}
        if sev_char in sev_map:
            return sev_map[sev_char]
    return ('UNKNOWN', 'white')


@chariot.group()
def report():
    """ Generate, validate, and manage reports and findings """
    pass


@report.command('risks')
@cli_handler
@click.option('--status', default='', help='Filter by status prefix (T=triage, O=open, D=demo, R=resolved, A=accepted, FP=false positive)')
@click.option('--asset', default='', help='Filter by asset (matches against dns or key)')
@click.option('--limit', default=100, type=int, help='Max results to show', show_default=True)
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def list_risks(sdk, status, asset, limit, json_out):
    """List risks/findings with formatted output.

    \b
    Guard risk statuses use compound codes: TH (triage high), OH (open high),
    DCD (demo confirmed), RH (resolved high), FP (false positive), etc.

    \b
    Examples:
        guard report risks
        guard report risks --status O
        guard report risks --asset "example.com" --json-output
    """
    params = {'key': '#risk'}

    resp = sdk.my(params)
    risks = resp.get('risks', resp.get('data', []))
    if not isinstance(risks, list):
        for key in resp:
            if isinstance(resp[key], list):
                risks = resp[key]
                break
        else:
            risks = []

    if status:
        risks = [r for r in risks if r.get('status', '').startswith(status.upper())]
    if asset:
        risks = [r for r in risks if asset.lower() in r.get('dns', '').lower() or asset.lower() in r.get('key', '').lower()]

    risks = risks[:limit]

    if json_out:
        print_json({'risks': risks, 'count': len(risks)})
        return

    if not risks:
        click.echo('No risks found.')
        return

    click.echo(click.style(f'{len(risks)} risk(s)', bold=True))
    click.echo(click.style('─' * 100, dim=True))

    for r in risks:
        status_code = r.get('status', '?')
        status_label, status_color = RISK_STATUS_COLORS.get(status_code, (status_code, 'white'))
        sev_label, sev_color = _get_severity(r)
        title = r.get('title', r.get('name', '?'))[:60]
        dns = r.get('dns', '')

        line = f"  {click.style(sev_label, fg=sev_color, bold=True):>15s}  "
        line += f"{click.style(status_label, fg=status_color):>20s}  "
        line += title
        if dns:
            line += click.style(f'  ({dns})', dim=True)
        click.echo(line)


@report.command('findings')
@cli_handler
@click.option('--status', default='', help='Status prefix filter (e.g. O for open, T for triage)')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def list_findings(sdk, status, json_out):
    """List findings grouped by severity.

    \b
    Examples:
        guard report findings
        guard report findings --status O
        guard report findings --status T
    """
    resp = sdk.my({'key': '#risk'})
    risks = resp.get('risks', resp.get('data', []))
    if not isinstance(risks, list):
        for key in resp:
            if isinstance(resp[key], list):
                risks = resp[key]
                break
        else:
            risks = []

    if status:
        risks = [r for r in risks if r.get('status', '').startswith(status.upper())]

    if json_out:
        print_json({'findings': risks, 'count': len(risks)})
        return

    if not risks:
        click.echo('No findings found.')
        return

    by_priority = {}
    for r in risks:
        p = r.get('priority', 99)
        by_priority.setdefault(p, []).append(r)

    total = len(risks)
    click.echo(click.style(f'{total} finding(s)', bold=True))

    for priority in sorted(by_priority.keys()):
        items = by_priority[priority]
        if not items:
            continue
        sev_label, sev_color = PRIORITY_LABELS.get(priority, (f'PRIORITY {priority}', 'white'))
        click.echo()
        click.echo(click.style(f'  {sev_label} ({len(items)})', fg=sev_color, bold=True))
        click.echo(click.style('  ' + '─' * 80, dim=True))
        for r in items:
            title = r.get('title', r.get('name', '?'))[:70]
            dns = r.get('dns', '')
            status_code = r.get('status', '')
            status_label, status_color = RISK_STATUS_COLORS.get(status_code, (status_code, 'white'))
            line = f'    {click.style(status_label, fg=status_color):>20s}  {title}'
            if dns:
                line += click.style(f'  ({dns})', dim=True)
            click.echo(line)


@report.command('summary')
@cli_handler
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def summary(sdk, json_out):
    """Show a summary of risks by severity and status.

    \b
    Examples:
        guard report summary
    """
    resp = sdk.my({'key': '#risk'})
    risks = resp.get('risks', resp.get('data', []))
    if not isinstance(risks, list):
        for key in resp:
            if isinstance(resp[key], list):
                risks = resp[key]
                break
        else:
            risks = []

    if json_out:
        print_json({'total': len(risks), 'risks': risks})
        return

    by_status = {}
    by_priority = {}
    for r in risks:
        s = r.get('status', '?')
        by_status[s] = by_status.get(s, 0) + 1
        p = r.get('priority', 99)
        by_priority[p] = by_priority.get(p, 0) + 1

    click.echo(click.style('Risk Summary', bold=True))
    click.echo(click.style('─' * 40, dim=True))
    click.echo(f'  Total: {len(risks)}')
    click.echo()

    click.echo(click.style('  By Severity:', bold=True))
    for priority in sorted(by_priority.keys()):
        count = by_priority[priority]
        if count:
            label, color = PRIORITY_LABELS.get(priority, (f'PRIORITY {priority}', 'white'))
            click.echo(f'    {click.style(label, fg=color, bold=True):>15s}: {count}')

    click.echo()
    click.echo(click.style('  By Status:', bold=True))
    for code, (label, color) in sorted(RISK_STATUS_COLORS.items()):
        count = by_status.get(code, 0)
        if count:
            click.echo(f'    {click.style(label, fg=color):>25s}: {count}')


@report.command()
@cli_handler
@click.option('--title', default='', help='Report title')
@click.option('--client', default='', help='Client name')
@click.option('--risks', default='', help='Risk filter (e.g., "status:OH" for open high risks)')
@click.option('--group-by-phase', is_flag=True, default=False, help='Group findings by phase tags')
@click.option('--format', 'fmt', type=click.Choice(['pdf', 'docx', 'html']), default='pdf',
              help='Output format', show_default=True)
@click.option('--output', default='', help='Output file path')
def generate(sdk, title, client, risks, group_by_phase, fmt, output):
    """ Generate a report

    Generate a report from Guard risk data. The report can be filtered
    by risk status and optionally grouped by phase tags.

    \b
    Example usages:
        - guard report generate --title "Q1 Pentest" --client "Acme Corp" --risks "status:OH"
        - guard report generate --risks "status:OH" --group-by-phase --format pdf
        - guard report generate --risks "status:OH" --format docx --output ./report.docx
    """
    body = dict(
        title=title,
        client=client,
        risks=risks,
        groupByPhase=group_by_phase,
        format=fmt,
    )

    result = sdk.post('export/report', body)

    if output:
        click.echo(f'Report saved to {output}')
    else:
        print_json(result)


@report.command()
@cli_handler
@click.option('--risks', default='', help='Risk filter to validate')
@click.option('--include-narratives', is_flag=True, default=False, help='Also check for narratives')
def validate(sdk, risks, include_narratives):
    """ Validate report requirements

    Check that the risks matching the filter have all required fields
    populated before generating a report. Optionally check for narratives.

    \b
    Example usages:
        - guard report validate --risks "status:OH"
        - guard report validate --risks "status:OH" --include-narratives
    """
    body = dict(
        risks=risks,
        includeNarratives=include_narratives,
    )

    result = sdk.post('validate-report', body)

    issues = result.get('issues', [])
    if not issues:
        click.echo('Validation passed. All report requirements are met.')
        return

    click.secho(f'Validation failed with {len(issues)} issue(s):\n', fg='red', err=True)
    for issue in issues:
        click.echo(f'  Issue: {issue.get("message", "Unknown issue")}', err=True)
        suggestion = issue.get('suggestion', '')
        if suggestion:
            click.echo(f'  Fix:   {suggestion}', err=True)
        click.echo('', err=True)

    sys.exit(1)
