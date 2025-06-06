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
