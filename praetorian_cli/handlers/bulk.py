import json
import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


def _read_records(file_path):
    """Read JSON records from a file path or stdin.

    Accepts either a JSON array or newline-delimited JSON objects.
    Returns a list of dicts. Raises click.ClickException on malformed
    input so @cli_handler can report the error without hard-exiting the
    process (sys.exit would bypass exception handling in library/console
    callers such as the interactive console passthrough).
    """
    if file_path == '-':
        text = sys.stdin.read()
    else:
        try:
            with open(file_path, 'r') as f:
                text = f.read()
        except FileNotFoundError:
            raise click.ClickException(f'File not found: {file_path}')
        except PermissionError:
            raise click.ClickException(f'Permission denied: {file_path}')

    text = text.strip()
    if not text:
        raise click.ClickException('Input is empty')

    if text.startswith('['):
        try:
            records = json.loads(text)
        except json.JSONDecodeError as e:
            raise click.ClickException(f'Invalid JSON array: {e}')
        if not isinstance(records, list):
            raise click.ClickException('Expected a JSON array of objects')
        for i, r in enumerate(records):
            if not isinstance(r, dict):
                raise click.ClickException(f'Record {i} is not a JSON object')
        return records

    records = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise click.ClickException(f'Line {lineno}: invalid JSON: {e}')
        if not isinstance(obj, dict):
            raise click.ClickException(f'Line {lineno}: expected a JSON object, got {type(obj).__name__}')
        records.append(obj)

    if not records:
        raise click.ClickException('No records found in input')
    return records


def _validate_required_keys(records, required_keys, entity_name):
    """Validate that all records contain the required keys."""
    for i, record in enumerate(records):
        missing = [k for k in required_keys if k not in record]
        if missing:
            raise click.ClickException(
                f'{entity_name} record {i}: missing required field(s): {", ".join(missing)}')


@chariot.group()
def bulk():
    """ Bulk operations on Guard entities """
    pass


@bulk.group()
def add():
    """ Bulk add entities from a file or stdin """
    pass


@add.command('asset')
@cli_handler
@click.option('--file', '-f', 'file_path', required=True,
              help='Path to JSON file with records, or "-" for stdin')
def bulk_add_asset(sdk, file_path):
    """ Bulk add assets from a file or stdin

    Each record must have "group" and "identifier" fields.
    Optional fields: type, status, surface, resource_type.

    \b
    Input format (JSON array or newline-delimited JSON):
        [
          {"group": "example.com", "identifier": "1.2.3.4"},
          {"group": "test.com", "identifier": "10.0.0.1", "surface": "internal"}
        ]

    \b
    Example usages:
        guard bulk add asset --file assets.json
        cat assets.jsonl | guard bulk add asset --file -
    """
    records = _read_records(file_path)
    _validate_required_keys(records, ['group', 'identifier'], 'Asset')
    click.echo(f'Submitting {len(records)} asset(s)...')
    result = sdk.assets.bulk_add(records)
    print_json(result)


@add.command('risk')
@cli_handler
@click.option('--file', '-f', 'file_path', required=True,
              help='Path to JSON file with records, or "-" for stdin')
def bulk_add_risk(sdk, file_path):
    """ Bulk add risks from a file or stdin

    Each record must have "asset_key", "name", and "status" fields.
    Optional fields: comment, capability, title, tags.

    \b
    Input format (JSON array or newline-delimited JSON):
        [
          {"asset_key": "#asset#example.com#1.2.3.4", "name": "CVE-2024-1234", "status": "O"}
        ]

    \b
    Example usages:
        guard bulk add risk --file risks.json
        cat risks.jsonl | guard bulk add risk --file -
    """
    records = _read_records(file_path)
    _validate_required_keys(records, ['asset_key', 'name', 'status'], 'Risk')
    click.echo(f'Submitting {len(records)} risk(s)...')
    result = sdk.risks.bulk_add(records)
    print_json(result)


@add.command('attribute')
@cli_handler
@click.option('--file', '-f', 'file_path', required=True,
              help='Path to JSON file with records, or "-" for stdin')
def bulk_add_attribute(sdk, file_path):
    """ Bulk add attributes from a file or stdin

    Each record must have "source_key", "name", and "value" fields.

    \b
    Input format (JSON array or newline-delimited JSON):
        [
          {"source_key": "#asset#example.com#1.2.3.4", "name": "port", "value": "443"}
        ]

    \b
    Example usages:
        guard bulk add attribute --file attributes.json
        cat attributes.jsonl | guard bulk add attribute --file -
    """
    records = _read_records(file_path)
    _validate_required_keys(records, ['source_key', 'name', 'value'], 'Attribute')
    click.echo(f'Submitting {len(records)} attribute(s)...')
    result = sdk.attributes.bulk_add(records)
    print_json(result)
