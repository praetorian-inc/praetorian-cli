import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


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
        return

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
