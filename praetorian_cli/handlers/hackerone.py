import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def hackerone():
    """HackerOne integration management"""
    pass


@hackerone.command('sync-scope')
@cli_handler
@praetorian_only
def sync_scope(chariot):
    """Synchronize HackerOne program scopes"""
    print_json(chariot.hackerone.sync_scope())


@hackerone.command('programs')
@cli_handler
@praetorian_only
def programs(chariot):
    """List HackerOne programs"""
    print_json(chariot.hackerone.programs())


@hackerone.command('scopes')
@cli_handler
@praetorian_only
@click.argument('handle')
def scopes(chariot, handle):
    """List scopes for a HackerOne program"""
    print_json(chariot.hackerone.program_scopes(handle))


@hackerone.command('weaknesses')
@cli_handler
@praetorian_only
@click.argument('handle')
def weaknesses(chariot, handle):
    """List weaknesses for a HackerOne program"""
    print_json(chariot.hackerone.program_weaknesses(handle))


@hackerone.command('comment')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.argument('message')
@click.option('--internal', is_flag=True, default=False, help='Mark as internal comment')
@click.option('--source', default='hacker-api', type=click.Choice(['hacker-api', 'org-api']),
              help='API source', show_default=True)
def comment(chariot, report_id, message, internal, source):
    """Add a comment to a HackerOne report"""
    print_json(chariot.hackerone.comment(report_id, message, internal=internal, source=source))


@hackerone.command('activities')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.option('--source', default='hacker-api', type=click.Choice(['hacker-api', 'org-api']),
              help='API source', show_default=True)
def activities(chariot, report_id, source):
    """List activities on a HackerOne report"""
    print_json(chariot.hackerone.activities(report_id, source=source))


@hackerone.command('severity')
@cli_handler
@praetorian_only
@click.argument('report_id')
@click.argument('rating', type=click.Choice(['none', 'low', 'medium', 'high', 'critical']))
def set_severity(chariot, report_id, rating):
    """Set severity on a HackerOne report"""
    print_json(chariot.hackerone.severity(report_id, rating))


@hackerone.command('bounty-catalog')
@cli_handler
@praetorian_only
def bounty_catalog(chariot):
    """Get the bounty catalog"""
    print_json(chariot.hackerone.bounty_catalog())
