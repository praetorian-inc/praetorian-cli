import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
@cli_handler
def unlink(ctx):
    """Unlink an account or integration from Chariot"""
    pass


integration = ['slack', 'jira', 'amazon', 'azure', 'gcp', 'github', 'ns1', 'crowdstrike']


@unlink.command('account')
@click.argument('account_id')
@cli_handler
def unlink_account(controller, account_id):
    """ Unlink an account """
    controller.unlink(account_id, "")


def unlink_integration(i):
    @unlink.command(i, help=f"Unlink {i} integration")
    @cli_handler
    @click.option('-i', '--id', default="", help="Provide an id if there are multiple instances")
    def command(controller, id):
        """ Unlink an integration """
        controller.unlink(i, id)


for i in integration:
    unlink_integration(i)
