import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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


def azure_sp_filename(client, credential_id, timestamp=None):
    """Return a unique Azure SP filename: {client}-{credentialId}-{timestamp}.json."""
    for value, label in ((client, 'client'), (credential_id, 'credential id')):
        if not isinstance(value, str) or '..' in value or '/' in value or '\\' in value:
            raise ValueError(f'Invalid {label} for Azure SP filename')
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if not isinstance(timestamp, str):
        timestamp = timestamp.strftime('%Y%m%dT%H%M%SZ')
    return f'{client}-{credential_id}-{timestamp}.json'


def write_azure_sp_file(path, client_id, tenant, client_assertion):
    """Write a one-entry Azure SP JSON file, created with mode 0o600."""
    path = Path(path)
    try:
        os.mkdir(path.parent, 0o700)
    except FileExistsError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump([{'client_id': client_id, 'tenant': tenant,
                    'client_assertion': client_assertion}], f)
    return path


def azure_credential_tenant(cred):
    """Resolve a tenant id from an Azure credential dict."""
    for key in ('tenantId', 'tenant', 'tenant_id'):
        value = cred.get(key)
        if value:
            return value
    account_key = cred.get('accountKey') or ''
    segments = account_key.rstrip('#').split('#')
    if len(segments) >= 2 and segments[-2] == 'azure':
        return segments[-1]
    return ''


def _azure_credential_list(credentials):
    return '\n'.join(
        f'  {c.get("credentialId", "")}  {azure_credential_tenant(c)}'
        for c in credentials
    )


def select_azure_credential(credentials, tenant=None, credential=None):
    """Pick one Azure credential; --tenant/--credential disambiguate, never guess."""
    if credential:
        matches = [c for c in credentials if c.get('credentialId') == credential]
        if not matches:
            error(
                f'No Azure credential matching --credential {credential!r}. Available:\n'
                + _azure_credential_list(credentials)
            )
        return matches[0]

    if tenant:
        matches = [c for c in credentials if azure_credential_tenant(c) == tenant]
        if not matches:
            error(
                f'No Azure credential matching --tenant {tenant!r}. Available:\n'
                + _azure_credential_list(credentials)
            )
        if len(matches) > 1:
            error(
                f'--tenant {tenant!r} matches more than one Azure credential. '
                'Pass --credential:\n' + _azure_credential_list(matches)
            )
        return matches[0]

    if len(credentials) > 1:
        error(
            'This account has more than one Azure credential. '
            'Select one with --tenant (and --credential if still ambiguous):\n'
            + _azure_credential_list(credentials)
        )

    return credentials[0]


def _azure_token_fields(cv):
    client_id = cv.get('clientId') or cv.get('client_id')
    tenant_id = cv.get('tenantId') or cv.get('tenant')
    assertion = cv.get('assertion') or cv.get('client_assertion')
    if not client_id or not tenant_id or not assertion:
        raise click.ClickException(
            'Azure credential is missing client id, tenant, or assertion.')
    return client_id, tenant_id, assertion


def run_az_login(client_id, tenant, assertion):
    """Run `az login --service-principal` with a federated token."""
    cmd = [
        'az', 'login', '--service-principal',
        '-u', client_id, '-t', tenant, '--federated-token', assertion,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise click.ClickException(
            'Azure CLI (az) is not installed. Install az and retry.')
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or '').strip()
        if assertion:
            detail = detail.replace(assertion, '[redacted]')
        raise click.ClickException(detail or 'az login failed')
    return completed


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


@access.command()
@cli_handler
@click.option('--org', default=None,
              help='GitHub organization to retrieve a token for. Required when the '
                   'account has more than one GitHub integration.')
@click.option('--format', 'output_format', default='token',
              type=click.Choice(['token', 'env']), show_default=True,
              help='Output shape. token: bare token on stdout. '
                   'env: export GITHUB_TOKEN / GH_TOKEN lines for `eval`.')
def github(sdk, org, output_format):
    """Retrieve a temporary GitHub App installation token.

    Looks up github integrations for the active account, asks the broker to
    mint a 1-hour App installation token, and prints it. Guard only brokers
    temporary App installation tokens; static PATs are refused server-side.

    The account is inherited from the top-level guard --account flag.

    \b
    Example usages:
        - guard access github
        - guard --account chariot+client@praetorian.com access github --org acme-inc
        - eval "$(guard access github --format env)" && gh auth status
    """
    account = sdk.keychain.account

    integrations, _ = sdk.integrations.list(name_filter='github')
    if not integrations:
        error(f'No GitHub integrations found for account {account}')

    integration = _select_github_integration(integrations, org)
    target = integration.get('value') or integration.get('key', '')

    token = _fetch_github_app_token(sdk, integration.get('key', ''), target)
    if not token:
        error(f'No GitHub App installation token was retrieved for {target}.')

    _print_github_token(token, output_format)


@access.command()
@cli_handler
@click.option('--account', default=None,
              help='Guard account email to discover Azure credentials for (also inherited from guard --account)')
@click.option('--tenant', default=None,
              help='Azure tenant ID. Required when the account has more than one Azure credential.')
@click.option('--credential', default=None,
              help='Azure credential UUID. Required when --tenant is still ambiguous.')
def azure(sdk, account, tenant, credential):
    """Log in to Azure CLI using a Guard Azure credential.

    Discovers Azure credentials, writes ~/.azure/{client}-{id}-{ts}.json, and
    runs `az login --service-principal`. --account is here or guard --account.

    \b
    Example usages:
        - guard --account chariot+client@praetorian.com access azure
        - guard access azure --tenant 11111111-1111-1111-1111-111111111111
        - guard access azure --credential caa85634-383f-4293-a995-b1427014408e
    """
    if account is None:
        account = sdk.keychain.account
    if account is None:
        raise click.ClickException('--account is required. Provide it here or as guard --account.')

    sdk.keychain.assume_role(account)
    prefix = extract_prefix(account)
    creds_response = sdk.credentials.list()
    credentials_list = creds_response[0] if isinstance(creds_response, tuple) else []
    azure_credentials = [c for c in credentials_list if c.get('type', '') == 'azure']

    if not azure_credentials:
        click.echo(f'No Azure credentials found for account {account}')
        return

    cred = select_azure_credential(azure_credentials, tenant=tenant, credential=credential)

    credential_id = cred.get('credentialId', '')
    category = cred.get('category', 'env-integration')
    result = sdk.credentials.get(credential_id, category, 'azure', 'token')
    client_id, tenant_id, assertion = _azure_token_fields(
        (result or {}).get('credentialValue') or {}
    )
    try:
        dest = Path.home() / '.azure' / azure_sp_filename(prefix, credential_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        write_azure_sp_file(dest, client_id, tenant_id, assertion)
    except FileExistsError:
        raise click.ClickException(
            f'Azure SP file already exists at {dest}. Retry the command.'
        ) from None
    try:
        run_az_login(client_id, tenant_id, assertion)
    except Exception:
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    click.echo(f'Wrote Azure service principal to {dest}')
    click.echo('Logged in with az login --service-principal')


def _select_github_integration(integrations, org):
    """Pick the one integration to mint a token for.

    A single integration is used as-is. With several, --org disambiguates by
    matching the integration value (a repo/org URL) or its trailing path
    segment; ambiguity without --org is an error rather than a guess.
    """
    if org:
        matches = [i for i in integrations if _matches_org(i, org)]
        if not matches:
            error(f'No GitHub integration matching --org {org!r}. Available:\n'
                  + _integration_list(integrations))
        if len(matches) > 1:
            error(f'--org {org!r} matches more than one GitHub integration:\n'
                  + _integration_list(matches))
        return matches[0]

    if len(integrations) > 1:
        error('This account has more than one GitHub integration. '
              'Select one with --org:\n' + _integration_list(integrations))

    return integrations[0]


def _matches_org(integration, org):
    value = (integration.get('value') or '').rstrip('/')
    org = org.strip().rstrip('/').lower()
    return value.lower() == org or value.rsplit('/', 1)[-1].lower() == org


def _integration_list(integrations):
    return '\n'.join(f'  {i.get("value") or i.get("key", "")}' for i in integrations)


def _fetch_github_app_token(sdk, integration_key, target):
    """Resolve a github credential via the broker.

    Github integrations don't use the standard "Asset + Credential record"
    pattern that from-parent walks: the OAuth installation flow stores the
    binding (installation_id, value) directly on the Account record, and the
    broker reads it from SSM keyed by the integration's own key
    (backend/pkg/services/account/integration_utils.go writes
    aws.Secrets.Set(account.Key, account.Secret); the github handler reads
    aws.Secrets.Get(request.CredentialID)). So for github, CredentialID *is*
    the integration key, and the right resolution is by-target.

    Returns the token string on success, None after printing a stderr message
    on failure.
    """
    try:
        result = sdk.credentials.get(
            integration_key, 'env-integration', 'github', ['token'],
            resolution='by-target',
        )
    except Exception as e:
        msg = str(e)
        if '[403]' in msg or 'unauthorized' in msg.lower():
            click.echo(
                f'{target}: Guard denied the request. End-user retrieval of '
                'GitHub App installation tokens may not be enabled on this '
                'deployment yet.',
                err=True,
            )
        else:
            click.echo(f'{target}: {msg.splitlines()[0]}', err=True)
        return None

    token = (result or {}).get('credentialValue', {}).get('github')
    if not isinstance(token, str) or not token:
        click.echo(f'{target}: broker returned no token', err=True)
        return None
    return token


def _print_github_token(token, output_format):
    if output_format == 'env':
        quoted = shlex.quote(token)
        click.echo(f'export GITHUB_TOKEN={quoted}')
        click.echo(f'export GH_TOKEN={quoted}')
    else:
        click.echo(token)
