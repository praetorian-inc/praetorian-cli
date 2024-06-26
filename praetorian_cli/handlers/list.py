from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.utils import key_set, paginate
from praetorian_cli.handlers.cli_decorators import cli_handler, list_options, page_options, plugins


@chariot.group()
@cli_handler
def list(ctx):
    """Get a list of resources from Chariot"""
    pass


list_filter = {'seeds': 'seed', 'assets': 'DNS', 'risks': 'seed', 'references': 'seed', 'attributes': 'seed',
               'jobs': 'updated', 'files': 'name', 'accounts': 'name', 'integrations': 'name',
               'definitions': 'name'}


def create_list_command(item_type, item_filter):
    @list.command(item_type, help=f"List {item_type}")
    @list_options(item_filter)
    @page_options
    @plugins
    def command(controller, filter, offset, details, page):
        if item_type == 'accounts' or item_type == 'integrations':
            paginate(controller, f'{key_set[item_type]}', item_type, filter, offset, details, page)
        else:
            paginate(controller, f'{key_set[item_type]}{filter}', item_type, "", offset, details, page)


for key, value in list_filter.items():
    create_list_command(key, value)
