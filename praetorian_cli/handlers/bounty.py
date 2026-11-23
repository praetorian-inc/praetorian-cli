"""Bug bounty findings feed across tenants, for HackerOne submission triage."""
import sys

import click
from rich.console import Console
from rich.table import Table

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json
from praetorian_cli.sdk.entities.bounty import LIVE_STATES, PROOF_ORDER, SORT_FIELDS, STATE_NAMES

STATE_CHOICES = {
    'live': LIVE_STATES,
    'triage': ('T',),
    'open': ('O',),
    'accepted': ('I',),
    'remediated': ('R',),
    'deleted': ('D',),
    'all': None,
}

SEVERITY_COLORS = {'critical': 'red', 'high': 'yellow', 'medium': 'cyan'}
PROOF_COLORS = {'verified': 'green', 'demonstrated': 'yellow', 'detected': 'white'}


@chariot.group()
def bounty():
    """Bug bounty findings feed across the BB tenants, for HackerOne submission triage."""
    pass


@bounty.command()
@cli_handler
@praetorian_only
@click.option('-P', '--program', 'programs', multiple=True,
              help='Only tenants whose program slug or account contains this text. Repeatable.')
@click.option('-d', '--details', is_flag=True, default=False, help='Output JSON instead of a table')
def programs(chariot, programs, details):
    """ List the bug bounty tenants you can access

    \b
    Example usages:
        - guard bounty programs
        - guard bounty programs -P costco -P lowes
        - guard bounty programs --details
    """
    tenants = chariot.bounty.tenants(list(programs))
    if details:
        print_json(dict(data=tenants))
        return
    for tenant in tenants:
        click.echo(f"{tenant['program']}\t{tenant['account']}")


@bounty.command()
@cli_handler
@praetorian_only
@click.option('-P', '--program', 'programs', multiple=True,
              help='Only tenants whose program slug or account contains this text. Repeatable.')
@click.option('-s', '--severity', default='critical,high', show_default=True,
              help='Comma-separated severities (critical, high, medium, low, info, exposure, or all).')
@click.option('--state', type=click.Choice(tuple(STATE_CHOICES)), default='live', show_default=True,
              help='Risk state to include. "live" is triage + open.')
@click.option('--proof', type=click.Choice(tuple(PROOF_ORDER)), default=None,
              help='Minimum proof level. "verified" = independently verified by the verification agent, '
                   '"demonstrated" = working proof attached, "detected" = scanner signal only.')
@click.option('--h1', 'hackerone', type=click.Choice(('any', 'submitted', 'unsubmitted')), default='any',
              show_default=True, help='Filter by whether the finding was already pushed to HackerOne.')
@click.option('--sort', 'sort_by', type=click.Choice(SORT_FIELDS), default='severity', show_default=True,
              help='Sort order. severity and proof rank the best submission candidates first.')
@click.option('--desc', is_flag=True, default=False, help='Reverse the sort order')
@click.option('-n', '--limit', type=int, default=0, help='Only show the first N findings (0 = all)')
@click.option('-d', '--details', is_flag=True, default=False, help='Output JSON instead of a table')
@click.option('--keys', is_flag=True, default=False, help='Output risk keys only, one per line')
@click.option('--workers', type=int, default=8, show_default=True, help='Tenants to query concurrently')
def findings(chariot, programs, severity, state, proof, hackerone, sort_by, desc, limit, details, keys, workers):
    """ Feed of findings across bug bounty tenants

    Pulls risks from every bug bounty tenant you can access, ranks them by
    severity and how well they are proven, and shows whether each one has
    already been pushed to HackerOne.

    \b
    Example usages:
        - guard bounty findings
        - guard bounty findings --proof verified --h1 unsubmitted
        - guard bounty findings -P bookingcom -P lowes --sort proof
        - guard bounty findings --severity all --state all -P zebra
        - guard bounty findings --details | jq '.data[] | select(.proof == "verified") | .key'
        - guard bounty findings --proof verified --keys
    """
    submitted = {'any': None, 'submitted': True, 'unsubmitted': False}[hackerone]
    results, errors = chariot.bounty.findings(
        programs=list(programs),
        severities=severity,
        states=STATE_CHOICES[state],
        proof=proof,
        submitted=submitted,
        sort_by=sort_by,
        descending=desc,
        workers=workers,
    )
    if limit and limit > 0:
        results = results[:limit]

    if details:
        output = dict(data=results)
        if errors:
            output['errors'] = errors
        print_json(output)
    elif keys:
        for finding in results:
            click.echo(finding['key'])
    elif sys.stdout.isatty():
        Console().print(build_findings_table(results))
    else:
        for line in findings_tsv(results):
            click.echo(line)

    for failure in errors:
        click.secho(f"WARNING: {failure['account']}: {failure['error']}", fg='yellow', err=True)


TSV_COLUMNS = ('program', 'severity', 'state', 'proof', 'h1', 'cvss', 'key')


def finding_row(finding):
    h1 = finding['hackerone']
    cvss = finding.get('cvss_score')
    return {
        'program': finding['program'],
        'severity': finding['severity'],
        'state': STATE_NAMES.get(finding['status'][0:1], finding['state']),
        'proof': finding['proof'],
        'h1': (h1.get('status') or 'submitted') if h1.get('submitted') else '-',
        'cvss': f'{cvss:.1f}' if isinstance(cvss, (int, float)) else '-',
        'key': finding['key'],
    }


def findings_tsv(findings):
    """ Tab-separated rows for piped output; same columns as the table, header first. """
    yield '\t'.join(TSV_COLUMNS)
    for finding in findings:
        row = finding_row(finding)
        yield '\t'.join(row[column] for column in TSV_COLUMNS)


def build_findings_table(findings):
    table = Table(title=f'{len(findings)} bug bounty findings', show_lines=False, expand=True)
    table.add_column('Program', style='bold', no_wrap=True)
    table.add_column('Severity', no_wrap=True)
    table.add_column('State', no_wrap=True)
    table.add_column('Proof', no_wrap=True)
    table.add_column('H1', no_wrap=True)
    table.add_column('CVSS', justify='right', no_wrap=True)
    table.add_column('Risk key', overflow='fold', ratio=1)

    for finding in findings:
        row = finding_row(finding)
        table.add_row(
            row['program'],
            click_color(row['severity'], SEVERITY_COLORS.get(row['severity'])),
            row['state'],
            click_color(row['proof'], PROOF_COLORS.get(row['proof'])),
            row['h1'],
            row['cvss'],
            row['key'],
        )
    return table


def click_color(text, color):
    return f'[{color}]{text}[/{color}]' if color else text
