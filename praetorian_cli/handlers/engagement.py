import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group()
def engagement():
    """ Manage engagements, customers, and vaults """
    pass


@engagement.command('list')
@cli_handler
def list_engagements(sdk):
    """ List accounts/engagements you have access to

    \b
    Example usage:
        guard engagement list
    """
    accounts, _ = sdk.accounts.list()
    if not accounts:
        click.echo('No accounts found.')
        return

    for acct in accounts:
        name = acct.get('name', '')
        member = acct.get('member', '')
        role = acct.get('role', acct.get('value', ''))
        click.echo(f'{name}\t{member}\t{role}')


@engagement.command('create-customer')
@cli_handler
@click.option('--email', required=True, help='Customer email (becomes their Guard username)')
@click.option('--name', 'display_name', required=True, help='Organization display name')
@click.option('--scan-level', type=click.Choice(['A', 'P', 'D', 'AL', 'AP', 'F']),
              default='A', show_default=True, help='Scan level (A=active, P=passive, D=disabled)')
@click.option('--type', 'customer_type', type=click.Choice(['ENGAGEMENT', 'MANAGED', 'SAAS', 'PILOT', 'FREEMIUM']),
              default='ENGAGEMENT', show_default=True, help='Customer type')
@click.option('--collaborator', multiple=True, help='Additional collaborator emails (format: email:role)')
def create_customer(sdk, email, display_name, scan_level, customer_type, collaborator):
    """ Create a new customer account on the Guard platform

    Creates a Cognito user, Guard account, and adds default collaborators.

    \b
    Example usages:
        guard engagement create-customer --email ops@acme.com --name "ACME Corp"
        guard engagement create-customer --email ops@acme.com --name "ACME Corp" --type MANAGED
        guard engagement create-customer --email ops@acme.com --name "ACME Corp" --collaborator "analyst@praetorian.com:admin"
    """
    body = {
        'username': email,
        'password': _generate_password(),
        'settings_display_name': display_name,
        'scan_level': scan_level,
        'customer_type': customer_type,
    }

    if collaborator:
        collabs = []
        for c in collaborator:
            if ':' in c:
                cemail, crole = c.rsplit(':', 1)
                collabs.append({'email': cemail, 'role': crole})
            else:
                collabs.append({'email': c, 'role': 'admin'})
        body['collaborators'] = collabs

    result = sdk.post('customer/onboard', body)
    click.echo(f'Customer created: {email} ({display_name})')
    print_json(result)


@engagement.command('create-vault')
@cli_handler
@click.option('--client', required=True, help='Client name (used in repo name)')
@click.option('--sow', required=True, help='SOW number')
@click.option('--sku', required=True, multiple=True,
              help='SKU code(s) — first determines template (WAPT, EXPT, INPT, AAWS, AIRT, PTFO, AISA, CRYP, CIAM, FPEN)')
@click.option('--github-user', required=True, help='GitHub username to add as admin')
def create_vault(sdk, client, sow, sku, github_user):
    """ Create an engagement vault repository on GitHub

    Creates a repo from the appropriate template based on SKU, adds the
    engineer as admin, and returns the repo URL.

    \b
    Example usages:
        guard engagement create-vault --client "acme" --sow "SOW-1234" --sku WAPT --github-user jdoe
        guard engagement create-vault --client "acme" --sow "SOW-1234" --sku EXPT --sku INPT --github-user jdoe
    """
    message = (
        f'Create a vault repository for client "{client}" with SOW number "{sow}". '
        f'SKUs: {", ".join(sku)}. Add GitHub user "{github_user}" as admin. '
        f'Use the github_vault tool.'
    )

    from praetorian_cli.handlers.agent import _send_and_poll
    _send_and_poll(sdk, message, timeout=120)


@engagement.command('onboard')
@cli_handler
@click.option('--email', required=True, help='Customer email')
@click.option('--name', 'display_name', required=True, help='Organization display name')
@click.option('--seed', multiple=True, help='Seed domains/CIDRs to add (e.g., example.com, 10.0.0.0/24)')
@click.option('--sow', default='', help='SOW file path in Guard storage to have Marcus read')
@click.option('--scan-level', default='A', show_default=True, help='Scan level')
@click.option('--type', 'customer_type', default='ENGAGEMENT', show_default=True, help='Customer type')
def onboard(sdk, email, display_name, seed, sow, scan_level, customer_type):
    """ Full engagement onboarding — create customer, add seeds, read SOW

    Combines customer creation, seed addition, and optional SOW ingestion
    in one command. This mirrors the engagement-coordinator agent workflow.

    \b
    Example usages:
        guard engagement onboard --email ops@acme.com --name "ACME Corp" --seed acme.com --seed 10.0.0.0/24
        guard engagement onboard --email ops@acme.com --name "ACME Corp" --seed acme.com --sow vault/sow.pdf
    """
    # Step 1: Create customer
    body = {
        'username': email,
        'password': _generate_password(),
        'settings_display_name': display_name,
        'scan_level': scan_level,
        'customer_type': customer_type,
    }

    click.echo(f'Creating customer: {email} ({display_name})...')
    try:
        result = sdk.post('customer/onboard', body)
        click.echo(f'Customer created.')
    except Exception as e:
        error(f'Customer creation failed: {e}', quit=False)
        return

    # Step 2: Switch to new customer account and add seeds
    if seed:
        click.echo(f'Adding {len(seed)} seeds...')
        for s in seed:
            try:
                # Add as seed via the SDK
                seed_type = 'asset'
                sdk.seeds.add(status='P', seed_type=seed_type, dns=s)
                click.echo(f'  Seed added: {s}')
            except Exception as e:
                click.echo(f'  Seed failed: {s} — {e}', err=True)

    # Step 3: If SOW provided, have Marcus read and analyze it
    if sow:
        click.echo(f'Having Marcus analyze SOW: {sow}...')
        from praetorian_cli.handlers.agent import _send_and_poll
        _send_and_poll(sdk, (
            f'Read the file at "{sow}" using the file_read tool. '
            f'This is a Statement of Work for {display_name}. '
            f'Extract scope information and add any discovered domains, IPs, and CIDRs as seeds. '
            f'Report what you found and created.'
        ), timeout=180)

    click.echo(f'\nOnboarding complete for {display_name} ({email}).')


def _generate_password(length=24):
    """Generate a Cognito-compliant password."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure Cognito requirements: upper, lower, digit, symbol
        if (any(c.isupper() for c in password) and
            any(c.islower() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in '!@#$%^&*' for c in password)):
            return password
