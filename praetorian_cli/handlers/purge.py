import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


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
    if not filter_key.strip():
        error('--filter must not be empty')

    if dry_run:
        click.echo(f'DRY RUN: Assets matching filter "{filter_key}":')
        results, _ = sdk.assets.list(filter_key, pages=100)
        if not results:
            click.echo('No matching assets found.')
            return
        for item in results:
            click.echo(f'  {item["key"]}')
        click.echo(f'\n{len(results)} asset(s) would be purged.')
        return

    if not force:
        click.echo(f'This will PERMANENTLY DELETE all assets matching "{filter_key}".')
        if not click.confirm('Are you sure?', default=False):
            click.echo('Purge cancelled.')
            return

    result = sdk.assets.purge(filter_key)
    click.echo(click.style('Assets purged.', fg='red'))
    print_json(result)


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
    if not filter_key.strip():
        error('--filter must not be empty')

    if dry_run:
        click.echo(f'DRY RUN: Risks matching filter "{filter_key}":')
        results, _ = sdk.risks.list(filter_key, pages=100)
        if not results:
            click.echo('No matching risks found.')
            return
        for item in results:
            click.echo(f'  {item["key"]}')
        click.echo(f'\n{len(results)} risk(s) would be purged.')
        return

    if not force:
        click.echo(f'This will PERMANENTLY DELETE all risks matching "{filter_key}".')
        if not click.confirm('Are you sure?', default=False):
            click.echo('Purge cancelled.')
            return

    result = sdk.risks.purge(filter_key)
    click.echo(click.style('Risks purged.', fg='red'))
    print_json(result)


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
    if not filter_key.strip():
        error('--filter must not be empty')

    if dry_run:
        click.echo(f'DRY RUN: Seeds matching filter "{filter_key}":')
        results, _ = sdk.seeds.list(key_prefix=filter_key, pages=100)
        if not results:
            click.echo('No matching seeds found.')
            return
        for item in results:
            click.echo(f'  {item["key"]}')
        click.echo(f'\n{len(results)} seed(s) would be purged.')
        return

    if not force:
        click.echo(f'This will PERMANENTLY DELETE all seeds matching "{filter_key}".')
        if not click.confirm('Are you sure?', default=False):
            click.echo('Purge cancelled.')
            return

    result = sdk.seeds.purge(filter_key)
    click.echo(click.style('Seeds purged.', fg='red'))
    print_json(result)


@chariot.group()
def tenant():
    """ Tenant administration commands """
    pass


@tenant.command()
@cli_handler
@click.option('--email', required=True, help='Email of the tenant to delete')
@click.option('--confirm-name', required=True,
              help='Type the exact tenant email to confirm deletion')
@click.option('--force', is_flag=True, default=False,
              help='Skip the additional interactive confirmation (typed name is still required)')
def delete(sdk, email, confirm_name, force):
    """ Delete a tenant account

    WARNING: This operation is IRREVERSIBLE. The tenant and ALL associated
    data will be permanently removed.

    Requires typing the exact tenant email via --confirm-name as a safety measure.

    \b
    Example usages:
        guard tenant delete --email customer@acme.com --confirm-name customer@acme.com
        guard tenant delete --email customer@acme.com --confirm-name customer@acme.com --force
    """
    if confirm_name != email:
        error(f'Confirmation mismatch: --confirm-name "{confirm_name}" does not match --email "{email}"')

    if not force:
        click.echo(f'This will PERMANENTLY DELETE tenant "{email}" and ALL associated data.')
        click.echo('This action CANNOT be undone.')
        if not click.confirm('Proceed with tenant deletion?', default=False):
            click.echo('Tenant deletion cancelled.')
            return

    result = sdk.accounts.delete_tenant(email)
    click.echo(click.style(f'Tenant deletion initiated for {email}.', fg='red'))
    print_json(result)


@tenant.command('status')
@cli_handler
@click.argument('deletion_id', required=True)
def tenant_status(sdk, deletion_id):
    """ Get the status of a tenant deletion request

    \b
    Argument:
        - DELETION_ID: the ID of the deletion request to check

    \b
    Example usages:
        guard tenant status del-123
    """
    result = sdk.accounts.get_tenant_deletion(deletion_id)
    print_json(result)
