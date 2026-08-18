import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group()
@cli_handler
def plextrac(sdk):
    """PlexTrac reporting integration"""
    pass


@plextrac.command('create-finding')
@cli_handler
@praetorian_only
@click.option('--risk-key', required=True, help='Risk key to push as a finding')
@click.option('--report-id', required=True, type=int, help='PlexTrac report ID')
def create_finding(sdk, risk_key, report_id):
    """Push a risk finding to a PlexTrac report"""
    print_json(sdk.plextrac.create_finding(risk_key, report_id))


@plextrac.command('reports')
@cli_handler
@praetorian_only
@click.option('--published', is_flag=True, default=False, help='Show only published reports')
def list_reports(sdk, published):
    """List PlexTrac reports"""
    print_json(sdk.plextrac.get_reports(published=published))


@plextrac.command('export')
@cli_handler
@click.option('--report-id', required=True, type=int, help='PlexTrac report ID to export')
def export_report(sdk, report_id):
    """Export a PlexTrac report as PDF"""
    print_json(sdk.plextrac.export(report_id))


@plextrac.command('connect')
@cli_handler
@praetorian_only
@click.option('--report-id', required=True, type=int, help='PlexTrac report ID to connect')
def connect(sdk, report_id):
    """Connect a PlexTrac report"""
    print_json(sdk.plextrac.connect_report(report_id))


@plextrac.command('disconnect')
@cli_handler
@praetorian_only
@click.option('--report-id', required=True, type=int, help='PlexTrac report ID to disconnect')
@click.confirmation_option(prompt='Are you sure you want to disconnect this report?')
def disconnect(sdk, report_id):
    """Disconnect a PlexTrac report"""
    print_json(sdk.plextrac.disconnect_report(report_id))


@plextrac.command('update-definition')
@cli_handler
@praetorian_only
@click.option('--risk-key', required=True, help='Risk key to update definition for')
def update_definition(sdk, risk_key):
    """Sync risk definition from PlexTrac"""
    print_json(sdk.plextrac.update_definition(risk_key))
