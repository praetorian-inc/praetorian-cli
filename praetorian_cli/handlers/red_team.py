import json
import re
import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


@chariot.group('red-team')
def red_team():
    """Manage red-team resources for the selected engagement without an LLM."""


@red_team.group()
def deployment():
    """Discover and manage the selected account's red-team deployment.

    Select the engagement with the root --profile / --account options.
    Changes always display a fresh redacted preview. Except for plan, they
    require default-no interactive confirmation or explicit --yes approval.
    """


@deployment.command('inventory')
@cli_handler
def inventory(sdk):
    """Show safe nodes/endpoints, version, collaborators and recorded history.

    Status is recorded, not live health. Missing deployments, unknown/stale
    status and unavailable outputs are returned explicitly in the JSON.
    """
    print_json(sdk.red_team_deployment.inventory())


@deployment.command('result')
@cli_handler
@click.option('--job-id', required=True, help='Exact job_id returned by the operation (quote #job# keys).')
@click.option('--enqueued', required=True, help='Exact enqueued timestamp returned with that job_id.')
def result(sdk, job_id, enqueued):
    """Show a specific job run; failed, superseded or unavailable exits nonzero."""
    _render_result(sdk.red_team_deployment.result(job_id, enqueued))


@deployment.command('launch')
@cli_handler
@click.option('--desired-id', required=True, help='Desired project ID; the server appends its random suffix.')
@click.option('-y', '--yes', is_flag=True, help='Explicitly approve this invocation after displaying its preview.')
def launch(sdk, desired_id, yes):
    """Preview, confirm and queue a new deployment for this engagement."""
    _operate(sdk, {'action': 'launch', 'desired_id': desired_id}, yes)


@deployment.command('plan')
@cli_handler
@click.option('--config-file', type=click.Path(exists=True, dir_okay=False, readable=True),
              help='BuilderState JSON file (not tfvars or Terraform state).')
@click.option('--config-json', help='Inline BuilderState JSON; prefer a file for sensitive inputs.')
@click.option('--tag', default='', help='Released infrastructure tag; omitted selects the backend default.')
@click.option('--force', is_flag=True, help='Override the backend live-campaign hold; does not approve apply.')
def plan(sdk, config_file, config_json, tag, force):
    """Preview and queue Terraform plan only; no approval or apply occurs.

    Supply exactly one of --config-file or --config-json. Plan results expose
    safe numeric counts when available, not a saved execution plan or raw logs.
    """
    _operate(sdk, {
        'action': 'plan',
        'state': _configuration(config_file, config_json),
        'tag': tag,
        'force': force,
    })


@deployment.command('apply')
@cli_handler
@click.option('--config-file', type=click.Path(exists=True, dir_okay=False, readable=True),
              help='BuilderState JSON file (not tfvars or Terraform state).')
@click.option('--config-json', help='Inline BuilderState JSON; prefer a file for sensitive inputs.')
@click.option('--tag', default='', help='Released infrastructure tag; omitted selects the backend default.')
@click.option('--force', is_flag=True, help='Override the backend live-campaign hold; confirmation is still required.')
@click.option('-y', '--yes', is_flag=True, help='Explicitly approve this invocation after displaying its preview.')
def apply(sdk, config_file, config_json, tag, force, yes):
    """Preview, confirm and queue apply using this exact configuration.

    Supply exactly one of --config-file or --config-json. Terraform computes
    its execution plan during apply; this does not apply a previously saved
    plan. Input or deployment-context drift requires a new preview/approval.
    """
    _operate(sdk, {
        'action': 'apply',
        'state': _configuration(config_file, config_json),
        'tag': tag,
        'force': force,
    }, yes)


@deployment.command('collaborators')
@cli_handler
@click.option('--collaborator', multiple=True, required=True, help='Complete desired collaborator email list; repeat for each email.')
@click.option('-y', '--yes', is_flag=True, help='Explicitly approve this invocation after displaying its preview.')
def collaborators(sdk, collaborator, yes):
    """Preview, confirm and replace the deployment's collaborator list."""
    _operate(sdk, {
        'action': 'update_collaborators',
        'collaborators': list(collaborator),
    }, yes)


@deployment.command('tag')
@cli_handler
@click.option('--tag', required=True, help='Released infrastructure tag to pin.')
@click.option('-y', '--yes', is_flag=True, help='Explicitly approve this invocation after displaying its preview.')
def tag(sdk, tag, yes):
    """Preview, confirm and update the pinned infrastructure revision."""
    _operate(sdk, {'action': 'update_infrastructure_tag', 'tag': tag}, yes)


@deployment.command('delete')
@cli_handler
@click.option('--force', is_flag=True, help='Override the backend live-campaign hold; confirmation is still required.')
@click.option('-y', '--yes', is_flag=True, help='Explicitly approve this invocation after displaying its preview.')
def delete(sdk, force, yes):
    """Preview and explicitly confirm deletion of deployment and infrastructure."""
    _operate(sdk, {'action': 'delete', 'force': force}, yes)


def _configuration(config_file, config_json):
    if (config_file is None) == (config_json is None):
        raise click.UsageError('Supply exactly one of --config-file or --config-json.')
    try:
        if config_file is not None:
            with open(config_file, encoding='utf-8') as stream:
                state = json.load(stream)
        else:
            state = json.loads(config_json)
    except (OSError, UnicodeError, ValueError):
        # Never echo parser input or file contents: configuration may be secret.
        raise click.ClickException('Could not read configuration as UTF-8 JSON.') from None
    if not isinstance(state, dict):
        raise click.UsageError('Configuration must be a BuilderState JSON object.')
    return state


def _operate(sdk, request, yes=False):
    # Parse configuration once. Preview and execute share these exact inputs;
    # neither a changed file nor a separately supplied hash can replace them.
    preview = sdk.red_team_deployment.preview(request)
    context_hash = preview.get('configuration_context_sha256')
    if (preview.get('action') != request['action']
            or not isinstance(context_hash, str)
            or re.fullmatch(r'[0-9a-f]{64}', context_hash) is None
            or not preview.get('tenant_id')
            or not isinstance(preview.get('deployment'), dict)
            or not isinstance(preview.get('change'), dict)
            or not isinstance(preview.get('infra'), dict)):
        raise click.ClickException('Incomplete or mismatched deployment preview; nothing was executed.')
    deployment_ref = preview['deployment']
    if request['action'] == 'launch':
        if (deployment_ref.get('desired_id') != request['desired_id']
                or not deployment_ref.get('suffix_policy')):
            raise click.ClickException('Launch preview does not match the requested deployment; nothing was executed.')
    elif not deployment_ref.get('project_id'):
        raise click.ClickException('Deployment identity is missing from the preview; nothing was executed.')
    if request['action'] in ('plan', 'apply'):
        input_hash = preview.get('input_sha256')
        if not isinstance(input_hash, str) or re.fullmatch(r'[0-9a-f]{64}', input_hash) is None:
            raise click.ClickException('Requested-input digest is missing from the preview; nothing was executed.')
    if request['action'] in ('launch', 'plan', 'apply', 'update_infrastructure_tag'):
        infra = preview['infra']
        if (not isinstance(infra.get('tag'), str)
                or not infra['tag']
                or not isinstance(infra.get('commit'), str)
                or re.fullmatch(r'[0-9a-fA-F]{40}', infra['commit']) is None):
            raise click.ClickException('Pinned infrastructure revision is missing from the preview; nothing was executed.')
        if request.get('tag') and infra['tag'] != request['tag']:
            raise click.ClickException('Pinned infrastructure tag does not match the requested tag; nothing was executed.')

    # Only this server-redacted projection is rendered, never the raw request.
    click.echo('Redacted deployment preview:')
    print_json(preview)
    if 'force' in request:
        click.echo(f"Live-campaign hold override (--force): {request['force']}")
    if request['action'] == 'apply':
        click.echo('Terraform computes its execution plan during apply; no saved plan is being applied.')
    if request['action'] != 'plan' and not yes:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise click.UsageError('Non-interactive changes require explicit --yes approval; nothing was executed.')
        click.confirm(
            f"Execute the displayed {request['action']} operation with these exact inputs and context?",
            default=False,
            abort=True,
        )
    _render_result(sdk.red_team_deployment.execute(request, context_hash))


def _render_result(operation):
    print_json(operation)
    status = operation.get('status')
    if status == 'enqueued':
        if not operation.get('job_id') or not operation.get('enqueued'):
            error('Queued operation did not return its job_id and enqueued run timestamp.')
        # Enqueued is not completed. The real identifiers above select the run
        # for `deployment result`; never report unconditional success here.
        return
    if status != 'succeeded':
        error('Deployment operation did not succeed; see the recorded status above.')
