import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, pagination
from praetorian_cli.handlers.utils import render_list_results, print_json, pagination_size


@chariot.command()
@cli_handler
@pagination
@click.option('-t', '--term', help='Enter a search term', required=True)
@click.option('-c', '--count', is_flag=True, default=False, help='Return statistics on search')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
def search(chariot, term, count, details, offset, page):
    """ Query Chariot for matches or counts using the search syntax

    \b
    Search syntax:

    \b
    - Search by prefix of the key of the entries:
        - "#asset#www"
        - "#asset#www.example.com#12.1."
        - "#risk#api.example.com"
    \b
    - Search by prefix of DNS:
        - "dns:www.example.com"
        - "dns:www."
        - "dns:https://github.com/praetorian-inc/praetorian-cli"

    \b
    - Search by prefix of IP address:
        - "ip:12.12.1."

    \b
    - Search by prefix of name:
        - "name:CVE-2024-"

    \b
    - Search by prefix of status:
        - "status:OH"
        - "status:JF"
        - "status:AH"
        - See https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/terminology.md for list of all statuses

    \b
    - Search by prefix of source:
        - "source:#asset#www.example.com#"
        - "source:#risk#www.example.com#"

    \b
    Example usages:
        - praetorian chariot search --term "status:OH"
        - praetorian chariot search --term "status:OH" --details --page all
        - praetorian chariot search --term "#asset#www.example.com"
        - praetorian chariot search --term "dns:https://github.com/praetorian-inc/"
    """
    if count:
        print_json(chariot.search.count(term))
    else:
        render_list_results(chariot.search.by_term(term, offset, pagination_size(page)), details)
