import os
from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group()
def export():
    """ Export data from Guard """
    pass


@export.command()
@cli_handler
@click.option('--client-name', required=True, help='Client organization name')
@click.option('--target', default='', help='Target scope')
@click.option('--start-date', default='', help='Engagement start date (ISO format)')
@click.option('--end-date', default='', help='Engagement end date (ISO format)')
@click.option('--output', '-o', default=os.getcwd(),
              help='Local directory to save the downloaded LOA')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def loa(sdk, client_name, target, start_date, end_date, output, json_out):
    """Export a Letter of Authorization (LOA).

    \b
    Examples:
        guard export loa --client-name "Acme Corp" --target "*.acme.com"
        guard export loa --client-name "Acme Corp" --start-date 2026-01-01 --end-date 2026-03-31
    """
    body = {
        'clientName': client_name,
    }
    if target:
        body['target'] = target
    if start_date:
        body['startDate'] = start_date
    if end_date:
        body['endDate'] = end_date

    result = sdk.post('export/loa', body)
    if json_out:
        print_json(result)
        return

    download_url = result.get('url') or result.get('download_url') or '' if isinstance(result, dict) else ''
    if download_url and output:
        import urllib.request
        resolved = os.path.realpath(os.path.expanduser(output))
        if os.path.isdir(resolved):
            resolved = os.path.join(resolved, 'loa.pdf')
        urllib.request.urlretrieve(download_url, resolved)
        click.echo(click.style('LOA saved to ', fg='green') + resolved)
    else:
        click.echo(click.style('LOA generated.', fg='green'))
        print_json(result)


@export.command('data')
@cli_handler
@click.argument('export_type', type=click.Choice(['csv', 'json', 'assets', 'risks', 'seeds', 'jobs']))
@click.option('--filter', 'filter_key', default='', help='Filter expression')
@click.option('--status', default='', help='Status filter')
@click.option('--output', '-o', default='', help='Output file path')
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def data_export(sdk, export_type, filter_key, status, output, json_out):
    """Export data by type (CSV, JSON, assets, risks, etc.).

    \b
    Examples:
        guard export data csv --filter "status:O" -o findings.csv
        guard export data risks --status O -o open_risks.json
        guard export data assets -o all_assets.json
    """
    params = {}
    if filter_key:
        params['filter'] = filter_key
    if status:
        params['status'] = status

    path = f'export/{quote(export_type, safe="")}'
    if params:
        qs = '&'.join(f'{k}={quote(v, safe="")}' for k, v in params.items())
        path = f'{path}?{qs}'

    result = sdk.get(path)
    if json_out or not output:
        print_json(result)
    else:
        import json
        resolved = os.path.realpath(os.path.expanduser(output))
        if not resolved.startswith(os.path.realpath(os.getcwd())):
            error(f'Output path must be under the current directory: {output}')
        with open(resolved, 'w') as f:
            if export_type == 'csv' and isinstance(result, str):
                f.write(result)
            else:
                json.dump(result, f, indent=2)
        click.echo(f'Exported to {resolved}')


@export.command('health')
@cli_handler
@click.option('--json-output', 'json_out', is_flag=True, default=False, help='Output raw JSON')
def health_report(sdk, json_out):
    """Generate a health report for the current account.

    \b
    Examples:
        guard export health
        guard export health --json-output
    """
    result = sdk.post('report/health', {})
    if json_out:
        print_json(result)
    else:
        click.echo(click.style('Health Report', bold=True))
        click.echo(click.style('─' * 60, dim=True))
        print_json(result)


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
