import os
from datetime import date
from time import sleep, time

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error


@chariot.group()
def export():
    """ Export data from Guard """
    pass


@export.command()
@cli_handler
@click.option('--title', required=True, help='Report title')
@click.option('--client-name', required=True, help='Client organization name')
@click.option('--status-filter', multiple=True, default=('O', 'T'),
              help='Risk status filter (repeatable). Default: O T')
@click.option('--risk-keys', multiple=True, default=(),
              help='Specific risk keys to include (repeatable). Default: all')
@click.option('--target', default='', help='Target/scope (e.g., example.com)')
@click.option('--start-date', default='', help='Engagement start date (ISO format)')
@click.option('--end-date', default='', help='Engagement end date (ISO format)')
@click.option('--report-date', default='', help='Report date (ISO format). Default: today')
@click.option('--draft/--no-draft', default=False, help='Add DRAFT watermark')
@click.option('--version', 'report_version', default='1.0', help='Report version string')
@click.option('--format', 'export_format', type=click.Choice(['pdf', 'zip']),
              default='pdf', help='Export format')
@click.option('--group-by', type=click.Choice(['attack_surface', 'tag']),
              default='attack_surface', help='Finding grouping strategy')
@click.option('--shared/--no-shared', default=False,
              help='Copy report to customer shared files')
@click.option('--executive-summary', default='',
              help='Path to executive summary .md file in Guard storage')
@click.option('--narratives', default='',
              help='Path to narratives .md file in Guard storage')
@click.option('--appendix', default='',
              help='Path to appendix .md file in Guard storage')
@click.option('--output', '-o', default=os.getcwd(),
              help='Local directory to save the downloaded report')
@click.option('--timeout', default=300, type=int,
              help='Max seconds to wait for report generation. Default: 300')
@click.option('--no-download', is_flag=True, default=False,
              help='Skip downloading the file; just print the job result')
def report(chariot, title, client_name, status_filter, risk_keys,
           target, start_date, end_date, report_date, draft,
           report_version, export_format, group_by, shared,
           executive_summary, narratives, appendix, output,
           timeout, no_download):
    """ Generate and download a PDF or ZIP report.

    Requires Praetorian engineer access. Initiates report generation,
    polls until the job completes, then downloads the file.

    The customer email is derived automatically from --account (the customer
    you are viewing) or the logged-in user's email.

    \b
    Example usages:
        guard --account customer@acme.com export report \\
            --title "Pentest Report" --client-name "Acme"

        guard --account customer@acme.com export report \\
            --title "Q1 Assessment" --client-name "Acme" \\
            --format zip --draft \\
            --status-filter O --status-filter T --status-filter R
    """
    customer_email = chariot.keychain.account or chariot.keychain.username()
    if not customer_email:
        error('Could not determine customer email. Use --account or configure a username.')

    if not report_date:
        report_date = date.today().isoformat()

    body = {
        'status_filter': list(status_filter),
        'config': {
            'title': title,
            'client_name': client_name,
            'report_date': report_date,
            'draft': draft,
            'version': report_version,
        },
        'shared_output': shared,
        'customer_email': customer_email,
        'export_format': export_format,
        'group_by': group_by,
    }

    if risk_keys:
        body['risk_keys'] = list(risk_keys)
    if target:
        body['config']['target'] = target
    if start_date:
        body['config']['start_date'] = start_date
    if end_date:
        body['config']['end_date'] = end_date
    if executive_summary:
        body['executive_summary_path'] = executive_summary
    if narratives:
        body['narratives_path'] = narratives
    if appendix:
        body['appendix_path'] = appendix

    click.echo(f'Starting {export_format.upper()} report generation for {customer_email}...')
    resp = chariot.post('export/report', body)

    job_key = resp.get('key')
    if not job_key:
        error('No job key returned from export/report endpoint.')

    click.echo(f'Job queued: {job_key}')
    click.echo(f'Polling for completion (timeout: {timeout}s)...')

    start_time = time()
    job = None
    while time() - start_time < timeout:
        job = chariot.jobs.get(job_key)
        if chariot.jobs.is_failed(job):
            message = job.get('message', 'unknown error')
            error(f'Report generation failed: {message}')
        if chariot.jobs.is_passed(job):
            break
        sleep(5)

    if not job or not chariot.jobs.is_passed(job):
        error(f'Report generation timed out after {timeout} seconds.')

    click.echo('Report generation complete.')

    config = job.get('config', {})
    output_path = config.get('output') or job.get('dns', '')

    if not output_path:
        error('Could not determine output file path from job.')

    if no_download:
        click.echo(f'Output path: {output_path}')
        return

    click.echo(f'Downloading {output_path}...')
    local_path = chariot.files.save(output_path, output)
    click.echo(f'Saved to {local_path}')
