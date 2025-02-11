import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def agent():
    """ A collection of AI features """
    pass


@agent.command()
@cli_handler
@click.argument('key')
def affiliation(sdk, key):
    """ Get affiliation data for risks and assets

    The AI agent retrieves affiliation information for the asset or risk. This command
    waits up to 3 minutes for the results.

    \b
    Example usages:
        - praetorian chariot agent affiliation "#risk#www.praetorian.com#CVE-2024-1234"
        - praetorian chariot agent affiliation "#asset#praetorian.com#www.praetorian.com"
    """
    click.echo("Polling for the affiliation data for up to 3 minutes.")
    click.echo(sdk.agents.affiliation(key))
