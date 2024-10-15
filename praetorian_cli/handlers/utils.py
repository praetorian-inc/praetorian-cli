import json

import click

from praetorian_cli.sdk.model.globals import Asset

AssetPriorities = {'comprehensive': Asset.ACTIVE_HIGH.value, 'standard': Asset.ACTIVE.value,
                   'discover': Asset.ACTIVE_LOW.value, 'frozen': Asset.FROZEN.value}


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
        click.echo(f'--offset "{json.dumps(offset)}"')


def pagination_size(page):
    return 1000 if page == 'all' else 1


def print_json(data):
    if data:
        click.echo(json.dumps(data, indent=4))


def error(message, quit=True):
    click.secho('ERROR: ', fg='red', nl=False)
    click.echo(message)
    if quit:
        exit(1)
