import sys
import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group('multipart')
def multipart():
    """Multipart file upload management"""
    pass


@multipart.command('create')
@cli_handler
@click.option('--name', required=True, help='File name/key')
@click.option('--praetorian', is_flag=True, default=False, help='Use praetorian file partition')
@click.option('--ttl', default=None, type=int, help='Time-to-live in seconds')
def create(chariot, name, praetorian, ttl):
    """Initiate a multipart upload and get an upload ID"""
    print_json(chariot.multipart.create(name, praetorian=praetorian, ttl=ttl))


@multipart.command('part-url')
@cli_handler
@click.option('--name', required=True, help='File name/key')
@click.option('--upload-id', required=True, help='Upload ID from create')
@click.option('--part-number', required=True, type=int, help='Part number (1-based)')
@click.option('--praetorian', is_flag=True, default=False, help='Use praetorian file partition')
def part_url(chariot, name, upload_id, part_number, praetorian):
    """Get a presigned URL for uploading a part"""
    print_json(chariot.multipart.get_part_url(name, upload_id, part_number, praetorian=praetorian))


@multipart.command('complete')
@cli_handler
def complete(chariot):
    """Complete a multipart upload (reads JSON from stdin)

    Stdin JSON: {"name": "...", "uploadId": "...", "parts": [{"partNumber": 1, "etag": "..."}]}
    """
    if sys.stdin.isatty():
        raise click.UsageError('Completion JSON is required via stdin')
    raw = sys.stdin.read().strip()
    if not raw:
        raise click.UsageError('Completion JSON is required via stdin')
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}')
    for key in ('name', 'uploadId', 'parts'):
        if body.get(key) is None:
            raise click.UsageError(f'Missing required key "{key}" in JSON input')
    print_json(chariot.multipart.complete(
        body.get('name'), body.get('uploadId'), body.get('parts'),
        praetorian=body.get('praetorian', False),
    ))


@multipart.command('abort')
@cli_handler
@click.option('--name', required=True, help='File name/key')
@click.option('--upload-id', required=True, help='Upload ID to abort')
@click.option('--praetorian', is_flag=True, default=False, help='Use praetorian file partition')
@click.confirmation_option(prompt='Are you sure you want to abort this upload?')
def abort(chariot, name, upload_id, praetorian):
    """Abort a multipart upload"""
    print_json(chariot.multipart.abort(name, upload_id, praetorian=praetorian))
