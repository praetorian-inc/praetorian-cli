import json

import click


def parse_configuration_value(
    entries = [], s_val=None, i_val=None, f_val=None):
    """Return a configuration value derived from CLI inputs."""
    has_entries = len(entries) > 0
    typed_values = {
        'string': s_val,
        'integer': i_val,
        'float': f_val,
    }

    if has_entries and any(value is not None for value in typed_values.values()):
        error('--entry cannot be combined with --string, --integer, or --float')

    if has_entries:
        return _parse_entry_dict(entries)

    provided = [(name, value) for name, value in typed_values.items() if value is not None]

    if not provided:
        error('Provide configuration data via --entry, --string, --integer, or --float')
    if len(provided) > 1:
        error('Specify only one of --string, --integer, or --float')

    value_type, raw_value = provided[0]
    return _cast_typed_value(value_type, raw_value)


def _parse_entry_dict(entries):
    parsed = {}

    for item in entries:
        key, value = _split_entry(item)
        if not key:
            error(f'Key cannot be empty: {item}')
        if not value:
            error(f'Value cannot be empty: {item}')
        parsed[key] = value
    return parsed


def _split_entry(item):
    if '=' not in item:
        error(f"Entry '{item}' is not in the format key=value")
    if item.count('=') > 1:
        error(f"Entry '{item}' contains multiple '=' characters. Format should be key=value")
    return item.split('=', 1)


def _cast_typed_value(value_type, raw_value):
    try:
        if value_type == 'integer':
            return int(raw_value)
        if value_type == 'float':
            return float(raw_value)
    except ValueError:
        error(f'{value_type} must be a valid {value_type}')
    return raw_value


def render_list_results(list_results, details):
    list_data, offset = list_results
    if details:
        output = dict(data=list_data)
        if offset:
            output['offset'] = offset
        print_json(output)
    else:
        for hit in list_data:
            click.echo(hit['key'])
    render_offset(offset)


def render_offset(offset):
    if offset:
        click.echo('There are more results. Add the following argument to the command to view them:')
        click.echo(f'--offset {json.dumps(offset)}')


def pagination_size(page):
    return 10000 if page == 'all' else 1


def print_json(data):
    if data:
        click.echo(json.dumps(data, indent=2))


def error(message, quit=True):
    click.secho('ERROR: ', fg='red', nl=False, err=True)
    click.echo(message, err=True)
    if quit:
        exit(1)
