import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


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
@click.option('--retest/--no-retest', default=False,
              help='Include retest status badges and sections')
@click.option('--version', 'report_version', default='1.0', help='Report version string')
@click.option('--sow', default='', help='Statement of Work identifier (expands %%SOW%% shortcode).')
@click.option('--footer', default='', help='Custom page-footer text (overrides the report title when set).')
@click.option('--confidential-label', 'confidential_label', default='', help='Confidentiality label shown on cover, header, and footer (defaults to "Confidential").')
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
           target, start_date, end_date, report_date, draft, retest,
           report_version, sow, footer, confidential_label, export_format, group_by, shared,
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
    customer_email = chariot.reports.customer_email()

    body = chariot.reports.build_export_body(
        title=title,
        client_name=client_name,
        customer_email=customer_email,
        status_filter=status_filter,
        risk_keys=risk_keys,
        target=target,
        start_date=start_date,
        end_date=end_date,
        report_date=report_date,
        draft=draft,
        retest=retest,
        version=report_version,
        sow=sow,
        footer=footer,
        confidential_label=confidential_label,
        export_format=export_format,
        group_by=group_by,
        shared_output=shared,
        executive_summary_path=executive_summary,
        narratives_path=narratives,
        appendix_path=appendix,
    )

    click.echo(f'Starting {export_format.upper()} report generation for {customer_email}...')
    job = chariot.reports.export(body, timeout=timeout)
    click.echo('Report generation complete.')

    if no_download:
        click.echo(f'Output path: {chariot.reports.output_path(job)}')
        return

    click.echo(f'Downloading {chariot.reports.output_path(job)}...')
    local_path = chariot.reports.download(job, output)
    click.echo(f'Saved to {local_path}')
