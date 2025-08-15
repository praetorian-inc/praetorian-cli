import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


@chariot.command()
@click.option('-d', '--details', is_flag=True, help='Show detailed information including filterable fields')
@click.option('-t', '--type', 'entity_type', help='Show schema for specific entity type')
@cli_handler
def schema(chariot, details, entity_type):
    """ Display available entity types and their schemas
    
    Display the schema information available at the /schema/ endpoint.
    By default shows just the type labels. Use --details to see filterable fields.
    
    \b
    Example usages:
        - praetorian chariot schema
        - praetorian chariot schema --details
        - praetorian chariot schema --type asset
        - praetorian chariot schema --type asset --details
    """
    
    schema_data = chariot.generic.get_schema(entity_type)

    if not schema_data:
        error(f"Entity type '{entity_type}' not found")

    if not details:
        show_keys(schema_data)
    else:
        print_json(schema_data)

def show_keys(data):
    for type_name in sorted(data.keys()):
        click.echo(type_name)