import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group()
def report():
    """ Generate and validate reports """
    pass


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
