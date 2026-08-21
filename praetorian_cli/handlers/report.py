import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error
from praetorian_cli.sdk.model.globals import Risk


# Severity suffixes used in Risk enum member names (see sdk/model/globals.py),
# in order of most- to least-specific so `str.endswith` matching below picks
# the right one (e.g. so 'CRITICAL' doesn't get shadowed by a shorter suffix).
_SEVERITY_STYLES = {
    'CRITICAL': ('CRITICAL', 'red'),
    'HIGH': ('HIGH', 'red'),
    'MEDIUM': ('MEDIUM', 'yellow'),
    'LOW': ('LOW', 'cyan'),
    'INFO': ('INFO', 'dim'),
    'EXPOSURE': ('EXPOSURE', 'blue'),
}


def _severity_for_enum_name(name):
    """Map a Risk enum member name (e.g. 'TRIAGE_HIGH') to a (label, color) severity pair."""
    for suffix, style in _SEVERITY_STYLES.items():
        if name.endswith(suffix):
            return style
    return None


# Built directly from the real Risk status enum so the codes/labels/colors here
# can't drift out of sync with sdk/model/globals.py. Codes are either 2 letters
# (status + severity, e.g. 'TH' = Triage High, 'OE' = Open Exposure) or 3
# letters for deletion reasons (status + severity + reason, e.g. 'DHF' =
# Deleted High False-positive).
# Severity (label, color) for each real status code, derived from the enum.
# Used by _get_severity() below so severity is never guessed from character
# position -- 2-letter and 3-letter codes both resolve correctly.
RISK_STATUS_SEVERITY = {
    member.value: _severity_for_enum_name(member.name)
    for member in Risk
}

RISK_STATUS_COLORS = {
    member.value: (
        member.name.replace('_', ' '),
        RISK_STATUS_SEVERITY[member.value][1] if RISK_STATUS_SEVERITY[member.value] else 'white',
    )
    for member in Risk
}

PRIORITY_LABELS = {
    10: ('CRITICAL', 'red'),
    20: ('HIGH', 'red'),
    30: ('MEDIUM', 'yellow'),
    40: ('LOW', 'cyan'),
    50: ('INFO', 'dim'),
}


def _get_severity(risk):
    """Derive severity from priority field, falling back to the risk's status code.

    Status codes come from the real Risk enum (sdk/model/globals.py): 2-letter
    codes are [status][severity] (e.g. 'OH' = Open High) and 3-letter deletion
    codes are [status][severity][reason] (e.g. 'DHF' = Deleted High
    False-positive) -- severity is NOT always the last character.
    """
    priority = risk.get('priority', 0)
    if priority in PRIORITY_LABELS:
        return PRIORITY_LABELS[priority]
    status = risk.get('status', '')
    severity = RISK_STATUS_SEVERITY.get(status)
    if severity:
        return severity
    return ('UNKNOWN', 'white')


@chariot.group()
def report():
    """ Generate, validate, and manage reports and findings """
    pass


@report.command('risks')
@cli_handler
@click.option('--status', default='', help='Filter by status prefix (T=triage, O=open, I=accepted, R=remediated, D=deleted)')
@click.option('--asset', default='', help='Filter by asset (matches against dns or key)')
@click.option('--limit', default=100, type=int, help='Max results to show', show_default=True)
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def list_risks(sdk, status, asset, limit, json_out):
    """List risks/findings with formatted output.

    \b
    Guard risk statuses use compound codes: TH (triage high), OH (open high),
    IH (accepted high), RH (remediated high), and 3-letter deletion codes
    like DHF (deleted high false-positive), DHD (deleted high duplicate), etc.

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

    # Map severity labels back to priority numbers so risks that lack a
    # recognised priority field but carry a valid status code are grouped
    # under the correct severity bucket instead of being dumped into
    # "PRIORITY 99".
    _sev_label_to_priority = {label: prio for prio, (label, _) in PRIORITY_LABELS.items()}

    by_priority = {}
    for r in risks:
        p = r.get('priority', 0)
        if p not in PRIORITY_LABELS:
            sev_label, _ = _get_severity(r)
            p = _sev_label_to_priority.get(sev_label, 99)
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
