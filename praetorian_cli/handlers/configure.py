import click
from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE


@click.command()
@click.pass_context
def configure(click_context):
    """Configure the CLI with API key authentication."""
    
    api_key_id = click.prompt("Enter your API Key ID")
    api_key_secret = click.prompt("Enter your API Key secret", hide_input=True)

    profile_name = click.prompt("Enter the profile name to configure", default=DEFAULT_PROFILE, show_default=True)
    url = click.prompt("Enter the URL of backend API", default=DEFAULT_API, show_default=True)
    client_id = click.prompt("Enter the client ID", default=DEFAULT_CLIENT_ID, show_default=True)
    assume_role = click.prompt("Enter the assume-role account, if any", default='', show_default=False)

    Keychain.configure(
        username=None,
        password=None,
        profile=profile_name,
        api=url,
        client_id=client_id,
        account=assume_role if assume_role else None,
        api_key_id=api_key_id,
        api_key_secret=api_key_secret
    )
