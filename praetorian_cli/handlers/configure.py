import click

from praetorian_cli.sdk.keychain import DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE


@click.command('configure')
@click.option('--email', required=True, help='Email you used to register for Chariot',
              prompt='Enter your email')
@click.option('--password', required=True, help='Password you used to register for Chariot', hide_input=True,
              prompt='Enter your password')
@click.option('--profile-name', required=True, help='Profile name. Default provided.', default=DEFAULT_PROFILE,
              prompt='Enter the profile name')
@click.option('--url', required=True, help='URL to the backend API. Default provided.', default=DEFAULT_API,
              prompt='Enter the URL of backend API')
@click.option('--client-id', required=True, help='Client ID of the backend. Default provided.',
              default=DEFAULT_CLIENT_ID, prompt='Enter the client ID')
@click.option('--assume-role', help='Email address of the account to assume-role into', default='',
              prompt='Enter the assume-role account, if any')
@click.pass_context
def configure(ctx, email, password, profile_name, url, client_id, assume_role):
    """ Configure the CLI """
    ctx.obj.configure(email, password, profile_name, url, client_id, assume_role)
