import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Import the existing 'add' group from the add handler
from praetorian_cli.handlers.add import add


@add.command('customer')
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
        - guard add customer --email ops@acme.com --name "ACME Corp"
        - guard add customer --email ops@acme.com --name "ACME Corp" --type MANAGED
        - guard add customer --email ops@acme.com --name "ACME Corp" --collaborator "analyst@praetorian.com:admin"
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


def _generate_password(length=24):
    """Generate a Cognito-compliant password."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in password) and
            any(c.islower() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in '!@#$%^&*' for c in password)):
            return password
