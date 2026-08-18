import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def osint():
    """ OSINT repository and technology operations """
    pass


@osint.command('guess-repo')
@cli_handler
@click.option('--cpe', default=None, help='CPE string (e.g., cpe:2.3:a:apache:httpd)')
@click.option('--technology-name', default=None, help='Technology name to look up')
def guess_repo(sdk, cpe, technology_name):
    """ Identify the source code repository for a technology via LLM

    \b
    At least one of --cpe or --technology-name is required.

    \b
    Example usages:
        guard osint guess-repo --cpe "cpe:2.3:a:apache:httpd"
        guard osint guess-repo --technology-name "OpenSSL"
    """
    if not cpe and not technology_name:
        raise click.UsageError('At least one of --cpe or --technology-name is required')
    print_json(sdk.osint.guess_repo(cpe=cpe, technology_name=technology_name))


@osint.command()
@cli_handler
@click.option('--repo-url', required=True, help='Public repository URL')
@click.option('--technology-key', default=None, help='Technology key to link')
@click.option('--goal', default=None, help='Scan goal description')
@click.option('--pipeline', default=None, help='Constantine pipeline name')
@click.option('--scan-mode', default=None, type=click.Choice(['auto', 'full', 'diff']),
              help='Scan mode')
def submit(sdk, repo_url, technology_key, goal, pipeline, scan_mode):
    """ Submit a repository for Constantine OSINT scanning

    \b
    Example usages:
        guard osint submit --repo-url "https://github.com/org/repo"
        guard osint submit --repo-url "https://github.com/org/repo" --pipeline premium-legacy
    """
    print_json(sdk.osint.submit(
        repo_url, technology_key=technology_key, goal=goal,
        pipeline=pipeline, scan_mode=scan_mode))


@osint.command('create-technology')
@cli_handler
@click.option('--cpe', required=True, help='CPE string for the technology')
def create_technology(sdk, cpe):
    """ Create a new technology in the OSINT partition from a CPE string

    \b
    Example usages:
        guard osint create-technology --cpe "cpe:2.3:a:apache:httpd:2.4.58"
    """
    print_json(sdk.osint.create_technology(cpe))
