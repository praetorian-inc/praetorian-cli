# AWS Credential Access Streamlining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the wrapper shell script and manual AWS config creation by adding a `credential-process` output format and a `configure credential` command that auto-generates `~/.aws/config` profiles.

**Architecture:** Two independent changes: (1) a new `credential-process` format in `Credentials._process_credential_output()` that outputs AWS-compatible JSON, and (2) a new `configure credential` Click subcommand that lists AWS credentials, discovers sub-accounts via boto3 Organizations, and writes `~/.aws/config` profiles pointing back at `guard get credential --format credential-process`.

**Tech Stack:** Python, Click (CLI framework), boto3 (AWS SDK — already a dependency), configparser (stdlib)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `praetorian_cli/sdk/entities/credentials.py` | Modify | Add `credential-process` format handling in `_process_credential_output()` |
| `praetorian_cli/handlers/configure.py` | Modify | Convert from standalone command to group, add `credential` subcommand |
| `praetorian_cli/main.py` | Modify | No structural change needed — `configure` is already registered as a command; converting it to a group is backwards-compatible in Click |
| `praetorian_cli/sdk/test/test_credential_process.py` | Create | Unit tests for credential-process format and prefix extraction |
| `praetorian_cli/sdk/test/test_configure_credential.py` | Create | Unit tests for AWS config generation logic |

---

### Task 1: Add `credential-process` format to Credentials SDK

**Files:**
- Modify: `praetorian_cli/sdk/entities/credentials.py:79-134`
- Create: `praetorian_cli/sdk/test/test_credential_process.py`

- [ ] **Step 1: Write the failing test for credential-process format**

Create `praetorian_cli/sdk/test/test_credential_process.py`:

```python
import json
import pytest

from praetorian_cli.sdk.entities.credentials import Credentials


class TestCredentialProcessFormat:

    def setup_method(self):
        self.credentials = Credentials(api=None)

    def test_credential_process_format_returns_aws_json(self):
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, 'credential-process')
        parsed = json.loads(result)
        assert parsed == {
            'Version': 1,
            'AccessKeyId': 'ASIATESTACCESSKEY',
            'SecretAccessKey': 'testsecretkey123',
            'SessionToken': 'testsessiontoken456',
            'Expiration': '2026-04-10T12:00:00Z'
        }

    def test_credential_process_format_from_list(self):
        """credential-process works when format is passed as a list (as the CLI does)."""
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, ['credential-process'])
        parsed = json.loads(result)
        assert parsed['Version'] == 1
        assert parsed['AccessKeyId'] == 'ASIATESTACCESSKEY'

    def test_credential_process_output_is_compact_json(self):
        """Output must be a single line of JSON (no pretty-printing) for AWS CLI compatibility."""
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, 'credential-process')
        assert '\n' not in result

    def test_format_output_returns_credential_process_string_as_is(self):
        """format_output should return a credential-process string unchanged."""
        raw = '{"Version":1,"AccessKeyId":"ASIATESTACCESSKEY","SecretAccessKey":"x","SessionToken":"y","Expiration":"z"}'
        output = self.credentials.format_output(raw)
        assert output == raw
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest praetorian_cli/sdk/test/test_credential_process.py -v`
Expected: FAIL — `_process_credential_output` doesn't handle `credential-process` format yet, so it falls through and returns the raw response dict.

- [ ] **Step 3: Implement credential-process format**

In `praetorian_cli/sdk/entities/credentials.py`, add the `credential-process` handler in `_process_credential_output()`. Insert this block **before** the final `return response` at line 134:

```python
        if primary_format == 'credential-process':
            cred = response['credentialValue']
            return json.dumps({
                'Version': 1,
                'AccessKeyId': cred['accessKeyId'],
                'SecretAccessKey': cred['secretAccessKey'],
                'SessionToken': cred['sessionToken'],
                'Expiration': cred['expiration']
            }, separators=(',', ':'))
```

Also add `import json` at the top of the file (currently it's only imported inside `format_output`). Move the `import json` from inside `format_output()` to the top-level imports:

```python
import json
import os
from pathlib import Path
```

And remove the `import json` line from inside `format_output()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest praetorian_cli/sdk/test/test_credential_process.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/sdk/entities/credentials.py praetorian_cli/sdk/test/test_credential_process.py
git commit -m "feat: add credential-process format to get credential"
```

---

### Task 2: Convert `configure` from command to group with subcommand

**Files:**
- Modify: `praetorian_cli/handlers/configure.py`

The existing `configure` is a standalone `@click.command()`. We need to convert it to a `@click.group()` so we can add `credential` as a subcommand, while keeping the existing keychain configuration as the default behavior.

- [ ] **Step 1: Write the failing test**

Add a test to verify the `configure` group has a `credential` subcommand. Add to `praetorian_cli/sdk/test/test_configure_credential.py`:

```python
import json
import os
import tempfile
import textwrap
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.configure import configure


class TestConfigureGroup:

    def test_configure_is_a_group(self):
        """configure must be a Click group so subcommands can be added."""
        import click
        assert isinstance(configure, click.Group)

    def test_configure_has_credential_subcommand(self):
        assert 'credential' in configure.commands
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest praetorian_cli/sdk/test/test_configure_credential.py::TestConfigureGroup -v`
Expected: FAIL — `configure` is currently a `click.command`, not a `click.group`.

- [ ] **Step 3: Convert configure to a group**

Rewrite `praetorian_cli/handlers/configure.py`:

```python
import click
from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE


@click.group(invoke_without_command=True)
@click.pass_context
def configure(click_context):
    """Configure the CLI or credential access."""
    if click_context.invoked_subcommand is None:
        # Default behavior: interactive keychain configuration (same as before)
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


def build_aws_config_profiles(account_email, prefix, credential_id, root_account_id, sub_accounts):
    """Build a list of (profile_name, profile_dict) tuples for AWS config.

    Args:
        account_email: The Guard account email (used in credential_process command)
        prefix: The profile name prefix
        credential_id: The credential UUID
        root_account_id: The root AWS account ID
        sub_accounts: List of dicts with 'Id' key from Organizations list_accounts,
                      or empty list if not an org.
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
            f'--type aws --format credential-process '
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


@configure.command()
@click.option('--account', required=True, help='Guard account email to discover AWS credentials for')
@click.option('--prefix', default=None, help='Override the profile name prefix (default: derived from email)')
@click.pass_context
def credential(click_context, account, prefix):
    """Generate AWS CLI config profiles from Guard credentials.

    Discovers AWS credentials for the given account, enumerates sub-accounts
    via Organizations (if applicable), and writes ~/.aws/config profiles that
    use guard as the credential_process.

    \b
    Example usages:
        - guard configure credential --account chariot+client@praetorian.com
        - guard configure credential --account chariot+client@praetorian.com --prefix myclient
    """
    import boto3

    from praetorian_cli.sdk.chariot import Chariot
    from praetorian_cli.sdk.keychain import Keychain

    # Get the Chariot SDK instance from parent context, or build one
    sdk = click_context.obj
    if sdk is None or not isinstance(sdk, Chariot):
        parent_ctx = click_context.parent
        if parent_ctx and isinstance(parent_ctx.obj, Chariot):
            sdk = parent_ctx.obj
        else:
            # Fallback: build from keychain in grandparent context
            gp = click_context.parent.parent if click_context.parent else None
            if gp and isinstance(gp.obj, dict) and 'keychain' in gp.obj:
                keychain = gp.obj['keychain']
                sdk = Chariot(keychain=keychain, proxy=gp.obj.get('proxy', ''))
            elif gp and isinstance(gp.obj, Chariot):
                sdk = gp.obj
            else:
                raise click.ClickException('Could not resolve SDK context. Ensure you are running under guard or praetorian chariot.')

    # Assume role into the target account
    sdk.keychain.assume_role(account)

    if prefix is None:
        prefix = extract_prefix(account)

    # List credentials and filter to AWS type
    creds_response = sdk.credentials.list()
    credentials_list = creds_response[0] if isinstance(creds_response, tuple) else creds_response.get('credentials', [])

    aws_credentials = [c for c in credentials_list if c.get('name', '') == 'amazon' or '#amazon#' in c.get('key', '')]

    if not aws_credentials:
        click.echo(f'No AWS credentials found for account {account}')
        return

    all_profiles = []

    for cred in aws_credentials:
        credential_id = cred.get('member', cred.get('key', '').split('#')[-1])
        credential_key = cred.get('key', '')
        root_account_id = extract_account_id(credential_key)

        # Fetch the root credential to get temp AWS creds
        try:
            result = sdk.credentials.get(credential_id, 'cloud', 'aws', 'token')
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
        )
        all_profiles.extend(profiles)

    if not all_profiles:
        click.echo(f'No AWS profiles could be generated for account {account}')
        return

    write_aws_config(all_profiles)
    click.echo(f'Wrote {len(all_profiles)} AWS profile(s) to ~/.aws/config:')
    for profile_name, _ in all_profiles:
        click.echo(f'  {profile_name}')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest praetorian_cli/sdk/test/test_configure_credential.py::TestConfigureGroup -v`
Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/handlers/configure.py praetorian_cli/sdk/test/test_configure_credential.py
git commit -m "feat: convert configure to group, add credential subcommand"
```

---

### Task 3: Unit tests for helper functions

**Files:**
- Modify: `praetorian_cli/sdk/test/test_configure_credential.py`

- [ ] **Step 1: Write tests for extract_prefix**

Append to `praetorian_cli/sdk/test/test_configure_credential.py`:

```python
from praetorian_cli.handlers.configure import extract_prefix, extract_account_id, build_aws_config_profiles, write_aws_config


class TestExtractPrefix:

    def test_standard_chariot_email(self):
        assert extract_prefix('chariot+proceptbiorobotics@praetorian.com') == 'proceptbiorobotics'

    def test_email_with_hyphens_and_underscores(self):
        assert extract_prefix('chariot+grant_street_group-ztw@praetorian.com') == 'grant_street_group-ztw'

    def test_email_without_plus(self):
        assert extract_prefix('user@example.com') == 'user'

    def test_email_with_multiple_plus_signs(self):
        assert extract_prefix('chariot+client+extra@praetorian.com') == 'client+extra'


class TestExtractAccountId:

    def test_standard_credential_key(self):
        key = '#account#chariot+grant_street_group-ztw@praetorian.com#amazon#325281727610'
        assert extract_account_id(key) == '325281727610'

    def test_credential_key_with_trailing_hash(self):
        key = '#account#chariot+client@praetorian.com#amazon#123456789012#'
        assert extract_account_id(key) == '123456789012'


class TestBuildAwsConfigProfiles:

    def test_single_root_account_no_org(self):
        profiles = build_aws_config_profiles(
            account_email='chariot+acme@praetorian.com',
            prefix='acme',
            credential_id='abc-123',
            root_account_id='111111111111',
            sub_accounts=[],
        )
        assert len(profiles) == 1
        name, data = profiles[0]
        assert name == 'acme-111111111111'
        assert 'guard --account chariot+acme@praetorian.com get credential abc-123' in data['credential_process']
        assert '--parameters accountId 111111111111' in data['credential_process']
        assert data['region'] == 'us-east-1'
        assert data['output'] == 'json'

    def test_org_with_sub_accounts(self):
        profiles = build_aws_config_profiles(
            account_email='chariot+acme@praetorian.com',
            prefix='acme',
            credential_id='abc-123',
            root_account_id='111111111111',
            sub_accounts=[
                {'Id': '111111111111', 'Name': 'Root'},
                {'Id': '222222222222', 'Name': 'Production'},
                {'Id': '333333333333', 'Name': 'Staging'},
            ],
        )
        assert len(profiles) == 3
        names = [p[0] for p in profiles]
        assert names == ['acme-111111111111', 'acme-222222222222', 'acme-333333333333']

    def test_root_not_duplicated_in_sub_accounts(self):
        """Root account ID appearing in sub_accounts should not create a duplicate profile."""
        profiles = build_aws_config_profiles(
            account_email='chariot+acme@praetorian.com',
            prefix='acme',
            credential_id='abc-123',
            root_account_id='111111111111',
            sub_accounts=[
                {'Id': '111111111111', 'Name': 'Root'},
                {'Id': '222222222222', 'Name': 'Dev'},
            ],
        )
        ids = [p[0] for p in profiles]
        assert ids.count('acme-111111111111') == 1


class TestWriteAwsConfig:

    def test_writes_new_config(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            config_path = f.name

        try:
            profiles = [
                ('acme-111111111111', {
                    'credential_process': 'guard get credential abc --type aws --format credential-process',
                    'region': 'us-east-1',
                    'output': 'json',
                }),
            ]
            write_aws_config(profiles, config_path=config_path)

            with open(config_path, 'r') as f:
                content = f.read()

            assert '[profile acme-111111111111]' in content
            assert 'credential_process = guard get credential abc' in content
            assert 'region = us-east-1' in content
        finally:
            os.unlink(config_path)

    def test_preserves_existing_profiles(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write('[profile existing-profile]\nregion = eu-west-1\noutput = text\n')
            config_path = f.name

        try:
            profiles = [
                ('new-profile-123', {
                    'credential_process': 'guard get credential xyz --type aws --format credential-process',
                    'region': 'us-east-1',
                    'output': 'json',
                }),
            ]
            write_aws_config(profiles, config_path=config_path)

            with open(config_path, 'r') as f:
                content = f.read()

            assert '[profile existing-profile]' in content
            assert 'eu-west-1' in content
            assert '[profile new-profile-123]' in content
        finally:
            os.unlink(config_path)

    def test_updates_existing_profile_with_same_name(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write('[profile acme-111111111111]\nregion = eu-west-1\noutput = text\n')
            config_path = f.name

        try:
            profiles = [
                ('acme-111111111111', {
                    'credential_process': 'guard get credential new-id --type aws --format credential-process',
                    'region': 'us-east-1',
                    'output': 'json',
                }),
            ]
            write_aws_config(profiles, config_path=config_path)

            with open(config_path, 'r') as f:
                content = f.read()

            assert content.count('[profile acme-111111111111]') == 1
            assert 'new-id' in content
            assert 'us-east-1' in content
        finally:
            os.unlink(config_path)

    def test_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'subdir', 'config')
            profiles = [
                ('test-123', {
                    'credential_process': 'guard get credential abc --type aws --format credential-process',
                    'region': 'us-east-1',
                    'output': 'json',
                }),
            ]
            write_aws_config(profiles, config_path=config_path)
            assert os.path.exists(config_path)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest praetorian_cli/sdk/test/test_configure_credential.py -v`
Expected: All tests PASS (implementation was done in Task 2).

- [ ] **Step 3: Commit**

```bash
git add praetorian_cli/sdk/test/test_configure_credential.py
git commit -m "test: add unit tests for configure credential helpers"
```

---

### Task 4: Verify CLI wiring end-to-end

**Files:**
- Modify: `praetorian_cli/sdk/test/test_configure_credential.py`

- [ ] **Step 1: Write CLI wiring tests**

Append to `praetorian_cli/sdk/test/test_configure_credential.py`:

```python
from click.testing import CliRunner


class TestConfigureCLIWiring:

    def test_configure_without_subcommand_prompts_for_keychain(self):
        """Running 'guard configure' with no subcommand should prompt for API key (backwards compat)."""
        runner = CliRunner()
        result = runner.invoke(configure, input='test-id\ntest-secret\n\n\n\n\n')
        # Should prompt for API Key ID
        assert 'API Key ID' in result.output

    def test_configure_credential_requires_account(self):
        """Running 'guard configure credential' without --account should fail."""
        runner = CliRunner()
        result = runner.invoke(configure, ['credential'])
        assert result.exit_code != 0
        assert 'account' in result.output.lower() or 'required' in result.output.lower()

    def test_configure_credential_help(self):
        runner = CliRunner()
        result = runner.invoke(configure, ['credential', '--help'])
        assert result.exit_code == 0
        assert '--account' in result.output
        assert '--prefix' in result.output
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest praetorian_cli/sdk/test/test_configure_credential.py::TestConfigureCLIWiring -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Add help test to existing CLI test suite**

In `praetorian_cli/sdk/test/test_z_cli.py`, find the `test_guard_cli` method and update the `configure --help` assertion. The existing test checks for `'Configure the CLI'` — update it to also check for `credential`:

Find this line in `test_guard_cli`:
```python
self.verify('configure --help', expected_stdout=['Configure the CLI'])
```

Replace with:
```python
self.verify('configure --help', expected_stdout=['Configure the CLI', 'credential'])
```

- [ ] **Step 4: Run the full CLI help test**

Run: `python -m pytest praetorian_cli/sdk/test/test_z_cli.py::TestZCli::test_guard_cli -v`
Expected: PASS (requires a configured profile; skip if no test environment available).

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/sdk/test/test_configure_credential.py praetorian_cli/sdk/test/test_z_cli.py
git commit -m "test: add CLI wiring tests for configure credential"
```

---

### Task 5: Manual integration verification

This task is a manual smoke test — no code changes.

- [ ] **Step 1: Verify credential-process format**

Run with a real credential (substitute your values):
```bash
guard --account chariot+proceptbiorobotics@praetorian.com get credential <uuid> --type aws --format credential-process --parameters accountId 900867815158
```

Expected: Compact JSON on a single line:
```json
{"Version":1,"AccessKeyId":"ASIA...","SecretAccessKey":"...","SessionToken":"...","Expiration":"..."}
```

- [ ] **Step 2: Verify configure credential**

```bash
guard configure credential --account chariot+proceptbiorobotics@praetorian.com
```

Expected: Output listing generated profiles, and `~/.aws/config` updated with new `[profile proceptbiorobotics-*]` sections.

- [ ] **Step 3: Verify AWS CLI uses the generated profiles**

```bash
aws --profile proceptbiorobotics-900867815158 sts get-caller-identity
```

Expected: Returns the caller identity for that account, confirming the `credential_process` integration works.

- [ ] **Step 4: Verify backwards compatibility**

```bash
guard configure
```

Expected: Interactive prompts for API Key ID, secret, etc. (same as before).
