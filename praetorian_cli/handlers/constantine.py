import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def constantine():
    """ Constantine exploit, patch, and validation pipelines """
    pass


@constantine.command()
@cli_handler
@click.option('--risk-keys', required=True, help='Comma-separated risk keys to exploit')
def exploit(sdk, risk_keys):
    """ Trigger exploit-only Constantine runs for risks

    \b
    Example usages:
        guard constantine exploit --risk-keys "#risk#example.com#CVE-2024-1234"
        guard constantine exploit --risk-keys "key1,key2,key3"
    """
    keys = [k.strip() for k in risk_keys.split(',') if k.strip()]
    print_json(sdk.constantine.exploit(keys))


@constantine.command()
@cli_handler
@click.option('--risk-keys', required=True, help='Comma-separated risk keys to patch')
def patch(sdk, risk_keys):
    """ Trigger patch-only Constantine runs for risks

    \b
    Example usages:
        guard constantine patch --risk-keys "#risk#example.com#CVE-2024-1234"
    """
    keys = [k.strip() for k in risk_keys.split(',') if k.strip()]
    print_json(sdk.constantine.patch(keys))


@constantine.command('patch-and-pr')
@cli_handler
@click.option('--risk-key', required=True, help='Single risk key to patch and create a PR for')
def patch_and_pr(sdk, risk_key):
    """ Patch a risk and create a GitHub pull request

    \b
    Example usages:
        guard constantine patch-and-pr --risk-key "#risk#example.com#CVE-2024-1234"
    """
    print_json(sdk.constantine.patch_and_pr(risk_key))


@constantine.command()
@cli_handler
@click.option('--risk-keys', required=True, help='Comma-separated risk keys to validate')
def validate(sdk, risk_keys):
    """ Validate previous exploit results for risks

    \b
    Example usages:
        guard constantine validate --risk-keys "#risk#example.com#CVE-2024-1234"
    """
    keys = [k.strip() for k in risk_keys.split(',') if k.strip()]
    print_json(sdk.constantine.validate(keys))


@constantine.command()
@cli_handler
def manifest(sdk):
    """ Get the Constantine pipeline manifest (presets and modules)

    \b
    Example usages:
        guard constantine manifest
    """
    print_json(sdk.constantine.manifest())
