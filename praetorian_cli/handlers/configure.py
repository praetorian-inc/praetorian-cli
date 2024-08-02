import click

from praetorian_cli.sdk.keychain import DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE, DEFAULT_USER_POOL_ID


@click.command('configure')
@click.option('--email', help='Email you used to register for Chariot', required=True,
              prompt='Enter your email')
@click.option('--password', help='Password you used to register for Chariot', required=True,
              prompt='Enter your password', hide_input=True)
@click.option('--profile-name', help='Profile name.', required=True,
              prompt='Enter the profile name', default=DEFAULT_PROFILE, show_default=True)
@click.option('--url', help='URL to the backend API. Default provided.', required=True,
              prompt='Enter the URL of backend API', default=DEFAULT_API)
@click.option('--client-id', help='Client ID of the backend. Default provided.', required=True,
              prompt='Enter the client ID', default=DEFAULT_CLIENT_ID)
@click.option('--user-pool-id', help='User pool ID of the backend. Default provided.', required=True,
              prompt='Enter the user pool ID', default=DEFAULT_USER_POOL_ID)
@click.option('--assume-role', help='Email address of the account to assume-role into', required=True,
              prompt='Enter the assume-role account, if any', default='')
@click.pass_context
def configure(ctx, email, password, profile_name, url, client_id, user_pool_id, assume_role):
    """ Configure the CLI """
    ctx.obj.configure(email, password, profile_name, url, client_id, user_pool_id, assume_role)
