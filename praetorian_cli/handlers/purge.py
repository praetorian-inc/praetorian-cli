import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


def _purge_command(sdk, entity_name, list_fn, purge_fn, filter_key, dry_run, force):
    """Shared logic for purge asset/risk/seed commands."""
    if not filter_key.strip():
        error('--filter must not be empty')
        return

    if dry_run:
        click.echo(f'DRY RUN: {entity_name}s matching filter "{filter_key}":')
        results, _ = list_fn(filter_key, pages=100)
        results = [r for r in results if r['key'].startswith(filter_key)]
        if not results:
            click.echo(f'No matching {entity_name.lower()}s found.')
            return
        for item in results:
            click.echo(f'  {item["key"]}')
        click.echo(f'\n{len(results)} {entity_name.lower()}(s) would be purged.')
        return

    if not force:
        click.echo(f'This will PERMANENTLY DELETE all {entity_name.lower()}s matching "{filter_key}".')
        if not click.confirm('Are you sure?', default=False):
            click.echo('Purge cancelled.')
            return

    result = purge_fn(filter_key)
    click.echo(click.style(f'{entity_name}s purged.', fg='red'))
    print_json(result)


@chariot.group('purge')
def purge_group():
    """ Irreversibly purge entities from Guard

    WARNING: Purge operations are destructive and cannot be undone.
    All commands require a non-empty --filter and prompt for confirmation.
    """
    pass


@purge_group.command('asset')
@cli_handler
@click.option('-f', '--filter', 'filter_key', required=True,
              help='Asset key prefix filter (e.g., "#asset#example.com")')
@click.option('--dry-run', is_flag=True, default=False,
              help='Preview what would be purged without making changes')
@click.option('--force', is_flag=True, default=False,
              help='Skip interactive confirmation (still requires --filter)')
def purge_asset(sdk, filter_key, dry_run, force):
    """ Purge assets matching a filter

    WARNING: This operation is IRREVERSIBLE. All matching assets will be
    permanently removed.

    \b
    Example usages:
        guard purge asset --filter "#asset#old-domain.com" --dry-run
        guard purge asset --filter "#asset#old-domain.com"
        guard purge asset --filter "#asset#old-domain.com" --force
    """
    _purge_command(sdk, 'Asset', sdk.assets.list, sdk.assets.purge, filter_key, dry_run, force)


@purge_group.command('risk')
@cli_handler
@click.option('-f', '--filter', 'filter_key', required=True,
              help='Risk key prefix filter (e.g., "#risk#example.com")')
@click.option('--dry-run', is_flag=True, default=False,
              help='Preview what would be purged without making changes')
@click.option('--force', is_flag=True, default=False,
              help='Skip interactive confirmation (still requires --filter)')
def purge_risk(sdk, filter_key, dry_run, force):
    """ Purge risks matching a filter

    WARNING: This operation is IRREVERSIBLE.

    \b
    Example usages:
        guard purge risk --filter "#risk#old-domain.com" --dry-run
        guard purge risk --filter "#risk#old-domain.com"
        guard purge risk --filter "#risk#old-domain.com" --force
    """
    _purge_command(sdk, 'Risk', sdk.risks.list, sdk.risks.purge, filter_key, dry_run, force)


@purge_group.command('seed')
@cli_handler
@click.option('-f', '--filter', 'filter_key', required=True,
              help='Seed key prefix filter')
@click.option('--dry-run', is_flag=True, default=False,
              help='Preview what would be purged without making changes')
@click.option('--force', is_flag=True, default=False,
              help='Skip interactive confirmation (still requires --filter)')
def purge_seed(sdk, filter_key, dry_run, force):
    """ Purge seeds matching a filter

    WARNING: This operation is IRREVERSIBLE.

    \b
    Example usages:
        guard purge seed --filter "#asset#old-domain.com" --dry-run
        guard purge seed --filter "#asset#old-domain.com"
        guard purge seed --filter "#asset#old-domain.com" --force
    """
    _purge_command(sdk, 'Seed',
                   lambda f, pages: sdk.seeds.list(key_prefix=f, pages=pages),
                   sdk.seeds.purge, filter_key, dry_run, force)
