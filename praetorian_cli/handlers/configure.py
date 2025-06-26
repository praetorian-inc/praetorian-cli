import click
from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE

@click.command()
@click.option('--email', is_flag=True, help='Use email/password authentication instead of API key')
@click.pass_context
def configure(click_context, email):
    """ Configure the CLI with API key (default) or email/password authentication """
    
    if email:
        email_address = click.prompt("Enter your email")
        password = click.prompt("Enter your password", hide_input=True)
        api_key_id = None
        api_key_secret = None
    else:
        api_key_id = click.prompt("Enter your API Key ID")
        api_key_secret = click.prompt("Enter your API Key secret", hide_input=True)
        email_address = None
        password = None

    profile_name = click.prompt("Enter the profile name to configure", default=DEFAULT_PROFILE, show_default=True)
    url = click.prompt("Enter the URL of backend API", default=DEFAULT_API, show_default=True)
    client_id = click.prompt("Enter the client ID", default=DEFAULT_CLIENT_ID, show_default=True)
    assume_role = click.prompt("Enter the assume-role account, if any", default='', show_default=False)

    Keychain.configure(email_address, password, profile_name, url, client_id, assume_role, api_key_id, api_key_secret)


