import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error


def extract_prefix(email):
    """Extract the profile prefix from a Guard account email.

    Takes the portion after '+' and before '@'.
    If no '+' exists, uses the full local part (before '@').

    Examples:
        chariot+proceptbiorobotics@praetorian.com -> proceptbiorobotics
        chariot+grant_street_group-ztw@praetorian.com -> grant_street_group-ztw
        user@example.com -> user
    """
    local_part = email.split('@')[0]
    if '+' in local_part:
        return local_part.split('+', 1)[1]
    return local_part


def extract_account_id(credential_key):
    """Extract the AWS account ID from a credential key.

    Keys look like: #account#chariot+client@praetorian.com#amazon#325281727610
    The account ID is the last segment.
    """
    return credential_key.rstrip('#').split('#')[-1]


def build_aws_config_profiles(account_email, prefix, credential_id, root_account_id, sub_accounts, category='env-integration'):
    """Build a list of (profile_name, profile_dict) tuples for AWS config.

    Args:
        account_email: The Guard account email (used in credential_process command)
        prefix: The profile name prefix
        credential_id: The credential UUID
        root_account_id: The root AWS account ID
        sub_accounts: List of dicts with 'Id' key from Organizations list_accounts,
                      or empty list if not an org.
        category: The credential category (e.g., 'env-integration', 'cloud')
    Returns:
        List of (profile_name, dict) where dict has credential_process, region, output keys.
    """
    profiles = []

    # Collect all account IDs (root + sub-accounts), deduplicated
    all_account_ids = [root_account_id]
    for acct in sub_accounts:
        if acct['Id'] != root_account_id:
            all_account_ids.append(acct['Id'])

    for account_id in all_account_ids:
        profile_name = f'{prefix}-{account_id}'
        credential_process = (
            f'guard --account {account_email} get credential {credential_id} '
            f'--category {category} --type aws --format credential-process '
            f'--parameters accountId {account_id}'
        )
        profiles.append((profile_name, {
            'credential_process': credential_process,
            'region': 'us-east-1',
            'output': 'json',
        }))

    return profiles


def write_aws_config(profiles, config_path=None):
    """Write AWS config profiles, preserving existing unrelated profiles.

    Args:
        profiles: List of (profile_name, profile_dict) tuples.
        config_path: Path to AWS config file. Defaults to ~/.aws/config.
    """
    from configparser import ConfigParser
    from pathlib import Path

    if config_path is None:
        config_path = os.path.join(Path.home(), '.aws', 'config')

    config = ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path)

    for profile_name, profile_data in profiles:
        section = f'profile {profile_name}'
        if not config.has_section(section):
            config.add_section(section)
        for key, value in profile_data.items():
            config.set(section, key, value)

    parent_dir = os.path.dirname(config_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(config_path, 'w') as f:
        config.write(f)


@chariot.group()
def access():
    """Configure credential access for cloud providers."""
    pass


@access.command()
@cli_handler
@click.option('--account', default=None, help='Guard account email to discover AWS credentials for (also inherited from guard --account)')
@click.option('--prefix', default=None, help='Override the profile name prefix (default: derived from email)')
def aws(sdk, account, prefix):
    """Generate AWS CLI config profiles from Guard credentials.

    Discovers AWS credentials for the given account, enumerates sub-accounts
    via Organizations (if applicable), and writes ~/.aws/config profiles that
    use guard as the credential_process.

    The --account can be provided here or as the top-level guard --account flag.

    \b
    Example usages:
        - guard --account chariot+client@praetorian.com access aws
        - guard access aws --account chariot+client@praetorian.com
        - guard access aws --account chariot+client@praetorian.com --prefix myclient
    """
    import boto3

    # Resolve account: explicit --account on this command, or inherited from guard --account
    if account is None:
        account = sdk.keychain.account
    if account is None:
        raise click.ClickException('--account is required. Provide it here or as guard --account.')

    sdk.keychain.assume_role(account)

    if prefix is None:
        prefix = extract_prefix(account)

    # List credentials and filter to AWS type
    creds_response = sdk.credentials.list()
    credentials_list = creds_response[0] if isinstance(creds_response, tuple) else []

    aws_credentials = [c for c in credentials_list if c.get('type', '') == 'aws']

    if not aws_credentials:
        click.echo(f'No AWS credentials found for account {account}')
        return

    all_profiles = []

    for cred in aws_credentials:
        credential_id = cred.get('credentialId', '')
        account_key = cred.get('accountKey', '')
        category = cred.get('category', 'env-integration')
        root_account_id = extract_account_id(account_key)

        # Fetch the root credential to get temp AWS creds
        try:
            result = sdk.credentials.get(credential_id, category, 'aws', ['token'])
        except Exception as e:
            click.echo(f'Warning: failed to get credential {credential_id}: {e}')
            continue

        access_key = result.get('credentialValue', {}).get('accessKeyId')
        secret_key = result.get('credentialValue', {}).get('secretAccessKey')
        session_token = result.get('credentialValue', {}).get('sessionToken')

        if not access_key:
            click.echo(f'Warning: credential {credential_id} returned no access key')
            continue

        # Try Organizations to discover sub-accounts
        sub_accounts = []
        try:
            org_client = boto3.client(
                'organizations',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name='us-east-1'
            )
            paginator = org_client.get_paginator('list_accounts')
            for page in paginator.paginate():
                sub_accounts.extend(page['Accounts'])
        except Exception:
            # Not an org account — that's fine, just use the root
            pass

        profiles = build_aws_config_profiles(
            account_email=account,
            prefix=prefix,
            credential_id=credential_id,
            root_account_id=root_account_id,
            sub_accounts=sub_accounts,
            category=category,
        )
        all_profiles.extend(profiles)

    if not all_profiles:
        click.echo(f'No AWS profiles could be generated for account {account}')
        return

    write_aws_config(all_profiles)
    click.echo(f'Wrote {len(all_profiles)} AWS profile(s) to ~/.aws/config:')
    for profile_name, _ in all_profiles:
        click.echo(f'  {profile_name}')


# Tokens minted by Guard's GitHub App installation flow start with `ghs_`.
# Static PATs (`ghp_` classic, `github_pat_` fine-grained) are refused so the
# CLI only ever surfaces 1-hour temporary tokens.
GITHUB_APP_TOKEN_PREFIX = 'ghs_'


@access.command()
@cli_handler
@click.option('--account', default=None,
              help='Guard account email (also inherited from guard --account).')
@click.option('--format', 'output_format', default='token',
              type=click.Choice(['token', 'env']), show_default=True,
              help='Output shape. token: bare token on stdout. '
                   'env: export GITHUB_TOKEN / GH_TOKEN lines for `eval`.')
def github(sdk, account, output_format):
    """Retrieve a temporary GitHub App installation token.

    Looks up github integrations for the active account, asks the broker to
    mint a 1-hour App installation token, and prints it. Only temporary App
    installation tokens are returned — static PATs are refused via the `ghs_`
    prefix check.

    \b
    Example usages:
        - guard access github
        - guard access github --format env
        - eval "$(guard access github --format env)" && gh auth status
    """
    if account is None:
        account = sdk.keychain.account
    if account is None:
        # error() raises SystemExit(1), bypassing the broad `except Exception`
        # in cli_decorators.handle_error that would otherwise swallow a
        # ClickException and let the process exit 0.
        error('--account is required. Provide it here or as guard --account.')
    sdk.keychain.assume_role(account)

    integrations, _ = sdk.integrations.list(name_filter='github')
    if not integrations:
        click.echo(f'No GitHub integrations found for account {account}', err=True)
        return

    printed = 0
    for integration in integrations:
        resource_key = integration.get('key', '')
        target = integration.get('value') or resource_key
        token = _fetch_github_app_token(sdk, resource_key, target)
        if token is None:
            continue
        if not token.startswith(GITHUB_APP_TOKEN_PREFIX):
            click.echo(
                f'Refusing token from {target}: prefix is not '
                f'{GITHUB_APP_TOKEN_PREFIX!r}; this looks like a static PAT '
                'rather than a 1-hour App installation token.',
                err=True,
            )
            continue
        _print_github_token(token, output_format)
        printed += 1

    if not printed:
        error('No temporary GitHub App installation tokens were retrieved.')


def _fetch_github_app_token(sdk, resource_key, target):
    """Resolve a github credential via the broker's from-parent path.

    The github credential is not surfaced in the per-account credentials list,
    so the only request shape that reaches the github handler is
    resolution=from-parent with the integration's resource_key. Returns the
    token string on success, None after printing a stderr message on failure.
    """
    try:
        result = sdk.credentials.get(
            '', 'env-integration', 'github', ['token'],
            resolution='from-parent', resource_key=resource_key,
        )
    except Exception as e:
        msg = str(e)
        if '[403]' in msg or 'unauthorized' in msg.lower():
            click.echo(
                f'Skipping {target}: Guard denied the request. End-user '
                'retrieval of GitHub App installation tokens may not be '
                'enabled on this deployment yet.',
                err=True,
            )
        else:
            click.echo(f'Skipping {target}: {msg.splitlines()[0]}', err=True)
        return None

    token = (result or {}).get('credentialValue', {}).get('github')
    if not token:
        click.echo(f'Skipping {target}: broker returned no token', err=True)
        return None
    return token


def _print_github_token(token, output_format):
    if output_format == 'env':
        click.echo(f'export GITHUB_TOKEN={token}')
        click.echo(f'export GH_TOKEN={token}')
    else:
        click.echo(token)
