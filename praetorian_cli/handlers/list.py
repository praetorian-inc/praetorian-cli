import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, list_params, pagination
from praetorian_cli.handlers.utils import render_offset, render_list_results, pagination_size


@chariot.group()
def list():
    """ Get a list of entities from Chariot """
    pass


@list.command()
@list_params('DNS')
def assets(chariot, filter, details, offset, page):
    """ List assets """
    render_list_results(chariot.assets.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('DNS of the associated assets')
def risks(chariot, filter, details, offset, page):
    """ List risks """
    render_list_results(chariot.risks.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('account email address')
def accounts(chariot, filter, details, offset, page):
    """ List accounts """
    render_list_results(chariot.accounts.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('integration name')
def integrations(chariot, filter, details, offset, page):
    """ List integrations """
    render_list_results(chariot.integrations.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('DNS of the job asset')
def jobs(chariot, filter, details, offset, page):
    """ List jobs """
    render_list_results(chariot.jobs.list(filter, offset, pagination_size(page)), details)


@list.command()
@list_params('file path')
def files(chariot, filter, details, offset, page):
    """ List files """
    render_list_results(chariot.files.list(filter, offset, pagination_size(page)), details)


@list.command()
@cli_handler
@pagination
@click.option('-f', '--filter', default="", help='Filter by definition name')
def definitions(chariot, filter, offset, page):
    """ List risk definitions """
    definitions, next_offset = chariot.definitions.list(filter, offset, pagination_size(page))
    click.echo('\n'.join(definitions))
    render_offset(next_offset)


@list.command()
@list_params('attribute name')
@click.option('-k', '--key', default=None, help='Filter by an asset or risk key')
def attributes(chariot, filter, key, details, offset, page):
    """ List attributes

        You can only filter by one of the following: attribute name, asset or risk
    """
    render_list_results(chariot.attributes.list(filter, key, offset, pagination_size(page)), details)
