import json

import click


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


def parse_name_value_fields(field_list, sep=':'):
    """Parse a sequence of name:value strings into a dict.
    
    - Splits on the first separator only to allow the value to contain it.
    - Emits a user-facing error and returns None on invalid input.

    Returns a dict on success, or None on error.
    """
    fields = {}
    for field in field_list:
        if sep in field:
            name, value = field.split(sep, 1)
            fields[name] = value
        else:
            error(f"Field '{field}' is not in the format name:value")
            return None
    return fields
