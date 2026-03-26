import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error
from praetorian_cli.sdk.model.globals import Kind


@chariot.command()
@cli_handler
@click.argument('term')
@click.option('-t', '--type', 'kind', type=click.Choice([s.value for s in Kind]), default=None,
              help='Limit search to a specific entity type')
@click.option('-l', '--limit', default=100, show_default=True,
              help='Maximum results per query (lower values avoid timeouts)')
@click.option('-d', '--details', is_flag=True, default=False,
              help='Show full JSON details for each result')
@click.option('--format', 'fmt', type=click.Choice(['text', 'json']), default='text', show_default=True,
              help='Output format')
def find(chariot, term, kind, limit, details, fmt):
    """ Fulltext search across Guard entities using Neo4j graph queries.

    \b
    Unlike the prefix-only `search` command, `find` performs contains/fulltext
    matching so you can locate entities by any substring in their key.

    \b
    Examples:
        guard find "example.com"
        guard find "CVE-2024" --type risk
        guard find "nginx" --type attribute --details
        guard find "10.0.1" --limit 50 --format json
    """
    term = term.strip()
    if not term:
        error('Search term cannot be empty.')

    all_results, _ = chariot.search.fulltext(term, kind=kind, limit=limit)

    if details or fmt == 'json':
        print_json(dict(data=all_results, count=len(all_results)))
    else:
        for hit in all_results:
            click.echo(hit.get('key', ''))

    if kind and len(all_results) >= limit:
        click.echo(
            f'Warning: results hit the limit ({limit}). '
            f'There may be more matches. Use --limit to increase or --type to narrow the search.',
            err=True
        )
