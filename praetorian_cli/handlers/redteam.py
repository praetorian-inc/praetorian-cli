import click
import json

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def redteam():
    """ Red team operations for terraform infrastructure management """
    pass


@redteam.command()
@cli_handler
def plan(sdk):
    """ Trigger a terraform plan operation

    This command initiates a terraform plan to preview infrastructure changes
    without actually applying them. The plan shows what actions Terraform will
    take to reach the desired state defined in your configuration.

    \b
    Example usage:
        praetorian chariot redteam plan
    """
    result = sdk.redteam.plan()
    click.echo(json.dumps(result, indent=2))


@redteam.command()
@cli_handler
def apply(sdk):
    """ Trigger a terraform apply operation

    This command initiates a terraform apply to execute the planned infrastructure
    changes. This will modify your actual infrastructure to match the desired state
    defined in your configuration.

    \b
    Example usage:
        praetorian chariot redteam apply
    """
    result = sdk.redteam.apply()
    click.echo(json.dumps(result, indent=2))


@redteam.command()
@click.option('--desired-project-id', '-p', required=True, help='GCP project ID for the red team engagement')
@cli_handler
def launch(sdk, desired_id):
    """ Trigger a red team operation launch

    This command initiates a red team operation launch to execute offensive
    security testing operations against your infrastructure.

    The project ID must meet GCP requirements:
    - 6-27 characters in length
    - Lowercase letters, numbers, and hyphens only
    - Must start with a letter
    - Cannot end with a hyphen

    \b
    Example usage:
        praetorian chariot redteam launch --desired-id client-name-2025-12-1234
    """
    result = sdk.redteam.launch(desired_id)
    click.echo(json.dumps(result, indent=2))


@redteam.command()
@cli_handler
def history(sdk):
    """ Retrieve historical red team operation records

    This command retrieves a list of all previous terraform plan and apply
    operations, including their status, timestamps, and who executed them.

    \b
    Example usage:
        praetorian chariot redteam history
    """
    result = sdk.redteam.history()
    click.echo(json.dumps(result, indent=2))


@redteam.command()
@click.option('--collaborators', '-c', multiple=True, required=True, help='Email addresses of collaborators (can be specified multiple times)')
@cli_handler
def collaborators(sdk, collaborators):
    """ Update collaborators for the current red team deployment

    This command updates the list of collaborators who have access to the
    red team project. Collaborators will be granted appropriate permissions
    to work on the red team infrastructure.

    You must provide at least one collaborator email address. You can specify
    multiple collaborators by using the -c flag multiple times.

    \b
    Example usage:
        praetorian chariot redteam collaborators -c alice@praetorian.com -c bob@praetorian.com
    """
    # Convert tuple to list for JSON serialization
    collaborator_list = list(collaborators)
    result = sdk.redteam.update_collaborators(collaborator_list)
    click.echo(json.dumps(result, indent=2))


@redteam.command()
@cli_handler
def details(sdk):
    """ Retrieve the current red team deployment configuration

    This command retrieves detailed information about the current red team
    deployment, including the GCP project ID, git hash of the infrastructure
    code, the principal who launched the deployment, collaborators with access,
    and deployment timestamps.

    \b
    Example usage:
        praetorian chariot redteam details
    """
    result = sdk.redteam.details()
    click.echo(json.dumps(result, indent=2))
