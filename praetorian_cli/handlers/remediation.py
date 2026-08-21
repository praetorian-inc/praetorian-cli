import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def remediation():
    """ Remediation patch selection and PR creation """
    pass


@remediation.command('select')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key to remediate')
@click.option('--finding-id', required=True, help='Finding ID within the risk')
@click.option('--option-id', required=True, help='Patch option ID to select')
@click.option('--strategy', default=None, help='Remediation strategy')
def select_patch(sdk, risk_key, finding_id, option_id, strategy):
    """ Save a patch selection for a risk finding

    \b
    Example usages:
        guard remediation select --risk-key "#risk#example.com#CVE-2024-1234" \\
            --finding-id "f1" --option-id "opt1"
        guard remediation select --risk-key "..." --finding-id "f1" \\
            --option-id "opt1" --strategy "minimal"
    """
    print_json(sdk.remediation.select_patch(
        risk_key, finding_id, option_id, strategy=strategy))


@remediation.command('clear')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key')
@click.option('--finding-id', required=True, help='Finding ID to clear patch selection for')
def clear_patch(sdk, risk_key, finding_id):
    """ Clear a patch selection for a risk finding

    \b
    Example usages:
        guard remediation clear --risk-key "#risk#example.com#CVE-2024-1234" --finding-id "f1"
    """
    print_json(sdk.remediation.clear_patch(risk_key, finding_id))


@remediation.command('create-pr')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key with a selected patch')
@click.option('--finding-id', required=True, help='Finding ID to create PR for')
def create_pr(sdk, risk_key, finding_id):
    """ Create a GitHub PR from a selected patch option

    \b
    Requires a patch to be selected first via 'guard remediation select'.

    \b
    Example usages:
        guard remediation create-pr --risk-key "#risk#example.com#CVE-2024-1234" --finding-id "f1"
    """
    print_json(sdk.remediation.create_pr(risk_key, finding_id))
