import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import render_list_results, print_json, error
from praetorian_cli.sdk.model.globals import Kind


@chariot.command()
@cli_handler
@click.option('--json', 'raw_json', help='Raw graph query as a JSON string (see sdk search.by_query)')
@click.option('--anchor', help='Exact key of the node to traverse from (shorthand mode)')
@click.option('--rel', 'rels', multiple=True,
              help='Relationship label(s) to follow, e.g. HAS_WEBPAGE. Omit to follow every edge type.')
@click.option('--neighbor', type=click.Choice([k.value for k in Kind]), help='Constrain the neighbor kind')
@click.option('-d', '--details', is_flag=True, default=False, help='Show full records instead of just keys')
def query(chariot, raw_json, anchor, rels, neighbor, details):
    """ Run an arbitrary graph query, including relationships.

    \b
    Two modes:

    \b
    - Raw: pass a full graph query as JSON (same shape the MCP tool uses).
        guard query --json '{"node": {"labels": ["Asset"], "relationships": [
          {"label": "HAS_VULNERABILITY", "target": {"labels": ["Risk"],
           "filters": [{"field": "priority", "operator": ">=", "value": 70}]}}]}}'

    \b
    - Shorthand: one hop from an anchor node to its neighbors.
        guard query --anchor "#webapplication#https://example.com"                         # every edge
        guard query --anchor "#asset#example.com#1.2.3.4" --rel HAS_WEBPAGE
        guard query --anchor "#webapplication#https://example.com" --rel HAS_WEBPAGE --neighbor webpage
        guard query --anchor "#asset#example.com#1.2.3.4" --rel HAS_VULNERABILITY --neighbor risk --details
    """
    if raw_json:
        render_list_results(chariot.search.by_query(raw_json), details)
        return

    if not anchor:
        error('Provide either --json, or --anchor (with optional --rel).')

    edges = chariot.search.relationships(anchor, list(rels), neighbor)
    if details:
        print_json(dict(data=edges))
    else:
        for e in edges:
            click.echo(f"{e['label']:20} {e['target'].get('key', '')}")
