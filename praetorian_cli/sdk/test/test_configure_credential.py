import os
import tempfile

import click
import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.configure import (
    configure,
    extract_prefix,
    extract_account_id,
    build_aws_config_profiles,
    write_aws_config,
)


class TestConfigureGroup:

    def test_configure_is_a_group(self):
        """configure must be a Click group so subcommands can be added."""
        assert isinstance(configure, click.Group)

    def test_configure_has_credential_subcommand(self):
        assert 'credential' in configure.commands


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
        assert '--category env-integration' in data['credential_process']
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


class TestConfigureCLIWiring:

    def test_configure_without_subcommand_prompts_for_keychain(self):
        """Running 'guard configure' with no subcommand should prompt for API key (backwards compat)."""
        runner = CliRunner()
        result = runner.invoke(configure, input='test-id\ntest-secret\n\n\n\n\n')
        assert 'API Key ID' in result.output

    def test_configure_credential_requires_account(self):
        """Running 'guard configure credential' without --account should fail."""
        runner = CliRunner()
        result = runner.invoke(configure, ['credential'])
        assert result.exit_code != 0

    def test_configure_credential_help(self):
        runner = CliRunner()
        result = runner.invoke(configure, ['credential', '--help'])
        assert result.exit_code == 0
        assert '--account' in result.output
        assert '--prefix' in result.output
