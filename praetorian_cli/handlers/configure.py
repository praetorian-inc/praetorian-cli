import click

from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE, DEFAULT_USER_POOL_ID


@click.command()
@click.option('--email', help='Email you used to register for Chariot', default='',
              prompt='Enter your email (Type ENTER if this is set in the PRAETORIAN_CLI_USERNAME environment variable, or if using SSO)')
@click.option('--password', help='Password you used to register for Chariot', default='',
              prompt='Enter your password (Type ENTER if this is set in the PRAETORIAN_CLI_PASSWORD environment variable, or if using SSO)',
              hide_input=True)
@click.option('--profile-name', help='Profile name.', required=True,
              prompt='Enter the profile name to configure', default=DEFAULT_PROFILE, show_default=True)
@click.option('--url', help='URL to the backend API. Default provided.', required=True,
              prompt='Enter the URL of backend API', default=DEFAULT_API)
@click.option('--client-id', help='Client ID of the backend. Default provided.', required=True,
              prompt='Enter the client ID', default=DEFAULT_CLIENT_ID)
@click.option('--user-pool-id', help='User pool ID of the backend. Default provided.', required=True,
              prompt='Enter the user pool ID', default=DEFAULT_USER_POOL_ID)
@click.option('--assume-role', help='Email address of the account to assume-role into', required=True,
              prompt='Enter the assume-role account, if any', default='')
@click.pass_context
def configure(click_context, email, password, profile_name, url, client_id, user_pool_id, assume_role):
    """ Configure the CLI """
    Keychain.configure(email, password, profile_name, url, client_id, user_pool_id, assume_role)
