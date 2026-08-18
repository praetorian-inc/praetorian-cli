import json
import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


def _read_json_body():
    data = sys.stdin.read().strip()
    if not data:
        raise click.UsageError('No JSON body provided on stdin')
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}')


@chariot.group()
def knossos():
    """ Knossos deception environment lifecycle """
    pass


# --- Profile subgroup ---

@knossos.group()
def profile():
    """ Knossos profile operations """
    pass


@profile.command('get')
@cli_handler
def profile_get(sdk):
    """ Get the current Knossos style profile

    \b
    Example usages:
        guard knossos profile get
    """
    print_json(sdk.knossos.profile())


@profile.command('infer')
@cli_handler
@click.option('--provider', default='aws', help='Cloud provider')
@click.option('--regions', default=None, help='Comma-separated regions to scope')
@click.option('--lookback-days', type=int, default=None,
              help='CloudTrail history days (default: 30)')
def profile_infer(sdk, provider, regions, lookback_days):
    """ Infer a style profile from cloud environment telemetry

    \b
    Example usages:
        guard knossos profile infer
        guard knossos profile infer --provider aws --regions us-east-1,us-west-2
        guard knossos profile infer --lookback-days 60
    """
    body = {'provider': provider}
    if regions:
        body['regions'] = [r.strip() for r in regions.split(',')]
    if lookback_days is not None:
        body['lookbackDays'] = lookback_days
    print_json(sdk.knossos.profile_infer(body))


@profile.command('versions')
@cli_handler
def profile_versions(sdk):
    """ List profile versions

    \b
    Example usages:
        guard knossos profile versions
    """
    print_json(sdk.knossos.profile_versions())


# --- Environment subgroup ---

@knossos.group('env')
def environment():
    """ Knossos decoy environment operations """
    pass


@environment.command()
@cli_handler
def generate(sdk):
    """ Generate a decoy environment from a JSON specification on stdin

    \b
    The JSON body supports: provider, seed, attackPaths, camouflageScale,
    historyLookbackDays, tuning, resourceCaps.

    \b
    Example usages:
        cat spec.json | guard knossos env generate
        echo '{"provider":"aws","attackPaths":[{"goal":"data_exfiltration","routes":2,"depth":[2,5]}]}' | guard knossos env generate
    """
    print_json(sdk.knossos.generate(_read_json_body()))


@environment.command('list')
@cli_handler
def env_list(sdk):
    """ List all decoy environments

    \b
    Example usages:
        guard knossos env list
    """
    print_json(sdk.knossos.environments())


@environment.command('get')
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
def env_get(sdk, env_id):
    """ Get a decoy environment manifest by ID

    \b
    Example usages:
        guard knossos env get --id abc123
    """
    print_json(sdk.knossos.environment(env_id))


@environment.command('delete')
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
@click.option('--force', is_flag=True, default=False,
              help='Skip confirmation prompt')
def env_delete(sdk, env_id, force):
    """ Delete a decoy environment

    \b
    Prompts for confirmation unless --force is passed.

    \b
    Example usages:
        guard knossos env delete --id abc123
        guard knossos env delete --id abc123 --force
    """
    if not force:
        click.confirm(f'Delete environment {env_id}?', abort=True)
    print_json(sdk.knossos.delete_environment(env_id))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
def emit(sdk, env_id):
    """ Emit Terraform HCL for a decoy environment

    \b
    Example usages:
        guard knossos env emit --id abc123
    """
    print_json(sdk.knossos.emit(env_id))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
@click.option('--refresh', is_flag=True, default=False,
              help='Force a live pricing refresh')
def cost(sdk, env_id, refresh):
    """ Get cost breakdown for a decoy environment

    \b
    Example usages:
        guard knossos env cost --id abc123
        guard knossos env cost --id abc123 --refresh
    """
    print_json(sdk.knossos.cost(env_id, refresh=refresh))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
def validate(sdk, env_id):
    """ Validate a decoy environment against the style profile

    \b
    Example usages:
        guard knossos env validate --id abc123
    """
    print_json(sdk.knossos.validate(env_id))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
def deploy(sdk, env_id):
    """ Deploy a decoy environment (export Terraform artifact)

    \b
    Example usages:
        guard knossos env deploy --id abc123
    """
    print_json(sdk.knossos.deploy(env_id))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
def status(sdk, env_id):
    """ Get deployment status for a decoy environment

    \b
    Example usages:
        guard knossos env status --id abc123
    """
    print_json(sdk.knossos.status(env_id))


@environment.command()
@cli_handler
@click.option('--id', 'env_id', required=True, help='Environment ID')
@click.option('--since', default=None, help='Events after this timestamp')
@click.option('--until', 'until_ts', default=None, help='Events before this timestamp')
@click.option('--lure-id', default=None, help='Filter by lure ID')
@click.option('--event-type', default=None, help='Filter by event type')
@click.option('--limit', type=int, default=None, help='Max results')
def events(sdk, env_id, since, until_ts, lure_id, event_type, limit):
    """ List interaction events for a decoy environment

    \b
    Example usages:
        guard knossos env events --id abc123
        guard knossos env events --id abc123 --event-type api_call --limit 100
    """
    print_json(sdk.knossos.events(
        env_id, since=since, until=until_ts, lure_id=lure_id,
        event_type=event_type, limit=limit))
