import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def agent():
    """ A collection of AI features """
    pass


@agent.command()
@cli_handler
@click.option('-r', '--risk', required=True, type=str, help='The key of the risk to be attributed')
def attribution(sdk, risk):
    """ Risk attribution

    The AI agent makes an attribution determination for the risk. This command
    waits up to 3 minutes for the results.

    \b
    Example usages:
        - praetorian chariot agent attribution -r #risk#www.praetorian.com#CVE-2024-1234
    """
    click.echo("Polling for the attribution result for up to 3 minutes.")
    click.echo(sdk.agents.attribution(risk))
