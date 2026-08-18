import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group()
@cli_handler
def hackerone(sdk):
    """HackerOne integration management"""
    pass


@hackerone.command('sync-scope')
@cli_handler
@praetorian_only
def sync_scope(sdk):
    """Synchronize HackerOne program scopes"""
    print_json(sdk.hackerone.sync_scope())


@hackerone.command('programs')
@cli_handler
@praetorian_only
def programs(sdk):
    """List HackerOne programs"""
    print_json(sdk.hackerone.programs())


@hackerone.command('scopes')
@cli_handler
@praetorian_only
@click.argument('handle')
def scopes(sdk, handle):
    """List scopes for a HackerOne program"""
    print_json(sdk.hackerone.program_scopes(handle))


@hackerone.command('weaknesses')
@cli_handler
@praetorian_only
@click.argument('handle')
def weaknesses(sdk, handle):
    """List weaknesses for a HackerOne program"""
    print_json(sdk.hackerone.program_weaknesses(handle))


@hackerone.command('comment')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.argument('message')
@click.option('--internal', is_flag=True, default=False, help='Mark as internal comment')
@click.option('--source', default='hacker-api', type=click.Choice(['hacker-api', 'org-api']),
              help='API source', show_default=True)
def comment(sdk, report_id, message, internal, source):
    """Add a comment to a HackerOne report"""
    print_json(sdk.hackerone.comment(report_id, message, internal=internal, source=source))


@hackerone.command('activities')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.option('--source', default='hacker-api', type=click.Choice(['hacker-api', 'org-api']),
              help='API source', show_default=True)
def activities(sdk, report_id, source):
    """List activities on a HackerOne report"""
    print_json(sdk.hackerone.activities(report_id, source=source))


@hackerone.command('severity')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.argument('rating', type=click.Choice(['none', 'low', 'medium', 'high', 'critical']))
def set_severity(sdk, report_id, rating):
    """Set severity on a HackerOne report"""
    print_json(sdk.hackerone.severity(report_id, rating))


@hackerone.command('bounty-catalog')
@cli_handler
@praetorian_only
def bounty_catalog(sdk):
    """Get the bounty catalog"""
    print_json(sdk.hackerone.bounty_catalog())
