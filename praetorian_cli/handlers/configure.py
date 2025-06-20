import click

from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE


@click.command()
@click.option('--email', help='Email you used to register for Chariot', default='',
              prompt='Enter your email (Type ENTER if this is set in the PRAETORIAN_CLI_USERNAME environment variable)')
@click.option('--password', help='Password you used to register for Chariot', default='',
              prompt='Enter your password (Type ENTER if this is set in the PRAETORIAN_CLI_PASSWORD environment variable)',
              hide_input=True)
@click.option('--profile-name', help='Profile name.', required=True,
              prompt='Enter the profile name to configure', default=DEFAULT_PROFILE, show_default=True)
@click.option('--url', help='URL to the backend API. Default provided.', required=True,
              prompt='Enter the URL of backend API', default=DEFAULT_API)
@click.option('--client-id', help='Client ID of the backend. Default provided.', required=True,
              prompt='Enter the client ID', default=DEFAULT_CLIENT_ID)
@click.option('--assume-role', help='Email address of the account to assume-role into', required=True,
              prompt='Enter the assume-role account, if any', default='')
@click.option('--api-key-id', help='API Key ID for authentication', default='')
@click.option('--api-key', help='API Key for authentication', default='', hide_input=True)
@click.pass_context
def configure(click_context, email, password, profile_name, url, client_id, assume_role, api_key_id, api_key):
    """ Configure the CLI """
    Keychain.configure(email, password, profile_name, url, client_id, assume_role, api_key_id, api_key)
