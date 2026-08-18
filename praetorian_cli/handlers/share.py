import sys
import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def share():
    """Manage secure share links"""
    pass


@share.command('create')
@cli_handler
@click.option('--name', required=True, help='Display name for the share link')
@click.option('--filter', 'query_filter', default=None, help='Query filter for shared data (JSON string)')
def create(chariot, name, query_filter):
    """Create a new share link (reads optional config JSON from stdin)"""
    body = {'name': name}
    raw = sys.stdin.read().strip()
    if raw:
        body.update(json.loads(raw))
    if query_filter:
        body['filter'] = json.loads(query_filter)
    print_json(chariot.share.create(body))


@share.command('list')
@cli_handler
def list_shares(chariot):
    """List all share links"""
    print_json(chariot.share.list())


@share.command('delete')
@cli_handler
@click.argument('share_id')
@click.confirmation_option(prompt='Are you sure you want to delete this share link?')
def delete(chariot, share_id):
    """Delete a share link"""
    print_json(chariot.share.delete(share_id))


@share.command('resolve')
@cli_handler
@click.argument('token')
def resolve(chariot, token):
    """Resolve a share link by its token"""
    print_json(chariot.share.resolve(token))
