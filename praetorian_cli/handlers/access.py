import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


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

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
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
