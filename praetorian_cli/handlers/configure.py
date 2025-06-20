import click
from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE

@click.command()
@click.pass_context
def configure(click_context):
    """ Configure the CLI with either email/password or API key """
    
    auth_method = click.prompt(
        "Choose authentication method",
        type=click.Choice(["email", "api-key"], case_sensitive=False),
        show_choices=True
    )

    email = password = api_key_id = api_key = ""

    if auth_method.lower() == "email":
        email = click.prompt("Enter your email")
        password = click.prompt("Enter your password", hide_input=True)
    else:
        api_key_id = click.prompt("Enter your API Key ID")
        api_key = click.prompt("Enter your API Key secret", hide_input=True)

    profile_name = click.prompt("Enter the profile name to configure", default=DEFAULT_PROFILE, show_default=True)
    url = click.prompt("Enter the URL of backend API", default=DEFAULT_API, show_default=True)
    client_id = click.prompt("Enter the client ID", default=DEFAULT_CLIENT_ID, show_default=True)
    assume_role = click.prompt("Enter the assume-role account, if any", default='', show_default=False)

    Keychain.configure(email, password, profile_name, url, client_id, assume_role, api_key_id, api_key)


