"""Unit tests for credential add/delete + WebApplication default-credential
('--secret') update — both at the SDK layer and through the CLI."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# Importing these for their side-effects: each handler module registers its
# Click commands on the `chariot` group via decorators at import time.
import praetorian_cli.handlers.add  # noqa: F401
import praetorian_cli.handlers.delete  # noqa: F401
import praetorian_cli.handlers.get  # noqa: F401
import praetorian_cli.handlers.update  # noqa: F401
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.sdk.entities.credentials import Credentials


# ---------------------------------------------------------------------------
# SDK-layer tests: verify the broker / asset request shapes
# ---------------------------------------------------------------------------

class TestCredentialsAdd:
    def test_add_builds_broker_request(self):
        api = MagicMock()
        api.post.return_value = {'ok': True}
        creds = Credentials(api=api)

        creds.add(
            resource_key='#webapplication#https://app.example.com',
            category='env-integration',
            type='web-auth',
            label='Prod token',
            parameters={'method': 'static-token', 'headers': {'Authorization': 'Bearer xyz'}},
        )

        api.post.assert_called_once_with('broker', {
            'Operation': 'add',
            'ResourceKey': '#webapplication#https://app.example.com',
            'Category': 'env-integration',
            'Type': 'web-auth',
            'Parameters': {
                'method': 'static-token',
                'headers': {'Authorization': 'Bearer xyz'},
                'label': 'Prod token',
            },
        })


class TestCredentialsGet:
    def test_get_builds_broker_request_with_resolution_by_target(self):
        """The broker rejects Get requests without Resolution (PR #5457). The
        CLI always passes an explicit credential_id, so Resolution must be
        'by-target' — anything else either ignores the id (global) or requires
        a ResourceKey the CLI doesn't have (from-parent)."""
        api = MagicMock()
        api.post.return_value = {'credentialValue': {'token': 'abc'}}
        creds = Credentials(api=api)

        creds.get(
            credential_id='e699e73e-e371-4117-9192-e32147dfe98c',
            category='env-integration',
            type='aws',
            format=['token'],
            accountId='123456789012',
        )

        api.post.assert_called_once_with('broker', {
            'Operation': 'get',
            'CredentialID': 'e699e73e-e371-4117-9192-e32147dfe98c',
            'Category': 'env-integration',
            'Type': 'aws',
            'Format': ['token'],
            'Resolution': 'by-target',
            'Parameters': {'accountId': '123456789012'},
        })

    def test_get_rewrites_credential_process_format_to_token(self):
        """`credential-process` is a client-side format — the broker sees
        'token' and the SDK assembles the AWS credential_process JSON from the
        response."""
        api = MagicMock()
        api.post.return_value = {
            'credentialValue': {
                'accessKeyId': 'ASIA...',
                'secretAccessKey': 'secret',
                'sessionToken': 'session',
                'expiration': '2026-04-10T12:00:00Z',
            }
        }
        creds = Credentials(api=api)

        creds.get(
            credential_id='abc-123',
            category='env-integration',
            type='aws',
            format=['credential-process'],
        )

        sent = api.post.call_args.args[1]
        assert sent['Format'] == ['token']
        assert sent['Resolution'] == 'by-target'

    def test_get_with_from_parent_sends_resource_key(self):
        """from-parent: broker walks DISCOVERED ancestors of ResourceKey for a
        matching credential. ResourceKey is required, CredentialID may be
        empty."""
        api = MagicMock()
        api.post.return_value = {'ok': True}
        creds = Credentials(api=api)

        creds.get(
            credential_id='',
            category='env-integration',
            type='aws',
            format=['token'],
            resolution='from-parent',
            resource_key='#asset#example.com#1.2.3.4',
        )

        api.post.assert_called_once_with('broker', {
            'Operation': 'get',
            'CredentialID': '',
            'Category': 'env-integration',
            'Type': 'aws',
            'Format': ['token'],
            'Resolution': 'from-parent',
            'Parameters': {},
            'ResourceKey': '#asset#example.com#1.2.3.4',
        })


class TestCredentialsDelete:
    def test_delete_builds_broker_request(self):
        api = MagicMock()
        api.delete.return_value = {'ok': True}
        creds = Credentials(api=api)

        creds.delete(
            credential_id='abc-123',
            resource_key='#webapplication#https://app.example.com',
            type='web-auth',
        )

        api.delete.assert_called_once_with('broker', {
            'CredentialID': 'abc-123',
            'ResourceKey': '#webapplication#https://app.example.com',
            'Type': 'web-auth',
        }, params={})


class TestAssetsUpdateSecret:
    def test_update_with_secret_passes_secret_through(self):
        api = MagicMock()
        api.upsert.return_value = {'ok': True}
        assets = Assets(api=api)

        assets.update('#webapplication#https://app.example.com', secret='cred-id-1')

        api.upsert.assert_called_once_with('asset', {
            'key': '#webapplication#https://app.example.com',
            'secret': 'cred-id-1',
        })

    def test_update_without_secret_omits_secret_field(self):
        api = MagicMock()
        api.upsert.return_value = {'ok': True}
        assets = Assets(api=api)

        assets.update('#asset#example.com#1.2.3.4', status='F')

        api.upsert.assert_called_once_with('asset', {
            'key': '#asset#example.com#1.2.3.4',
            'status': 'F',
        })


# ---------------------------------------------------------------------------
# CLI-layer tests: verify Click wiring + arg parsing for the new commands
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.credentials.add.return_value = {'ok': True}
    sdk.credentials.delete.return_value = {'ok': True}
    sdk.credentials.get.return_value = {'credentialValue': {'token': 'abc'}}
    sdk.credentials.format_output.side_effect = lambda r: str(r)
    sdk.assets.update.return_value = {'ok': True}
    return sdk


def _invoke(runner, fake_sdk, argv):
    """Invoke the CLI with a patched SDK factory (mirrors test_run_cli.py)."""
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, catch_exceptions=False)


class TestAddCredentialGeneric:
    """The pre-existing `guard add credential ...` flow still works after the
    Click-group conversion."""

    def test_generic_add_calls_sdk_with_parsed_params(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'add', 'credential',
            '-r', '#asset#example.com#1.2.3.4',
            '-c', 'env-integration',
            '-t', 'active-directory',
            '-l', 'Robb Stark',
            '-p', 'username=robb.stark',
            '-p', 'password=sexywolfy',
            '-p', 'domain=north.sevenkingdoms.local',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.add.assert_called_once_with(
            '#asset#example.com#1.2.3.4',
            'env-integration',
            'active-directory',
            'Robb Stark',
            {
                'username': 'robb.stark',
                'password': 'sexywolfy',
                'domain': 'north.sevenkingdoms.local',
            },
        )

    def test_generic_add_rejects_missing_required(self, runner, fake_sdk):
        # Missing --label
        result = _invoke(runner, fake_sdk, [
            'add', 'credential',
            '-r', '#asset#x#y',
            '-c', 'env-integration',
            '-t', 'active-directory',
        ])
        assert result.exit_code != 0
        assert '--label' in result.output

    def test_generic_add_rejects_bad_param_format(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'add', 'credential',
            '-r', '#asset#x#y',
            '-c', 'env-integration',
            '-t', 'static-token',
            '-l', 'Test',
            '-p', 'no-equals-sign',
        ])
        assert result.exit_code != 0
        assert 'key=value' in result.output


class TestAddCredentialWebauth:
    def test_webauth_subcommand_builds_static_token_request(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'add', 'credential', 'webauth',
            '-k', '#webapplication#https://app.example.com',
            '-l', 'Prod token',
            '-H', 'Authorization=Bearer abc123',
            '-H', 'X-Tenant=acme',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.add.assert_called_once_with(
            '#webapplication#https://app.example.com',
            'env-integration',
            'web-auth',
            'Prod token',
            {
                'method': 'static-token',
                'headers': {
                    'Authorization': 'Bearer abc123',
                    'X-Tenant': 'acme',
                },
            },
        )

    def test_webauth_preserves_equals_in_header_value(self, runner, fake_sdk):
        """Header values can themselves contain '=' (e.g. base64 padding)."""
        _invoke(runner, fake_sdk, [
            'add', 'credential', 'webauth',
            '-k', '#webapplication#https://app.example.com',
            '-l', 'Encoded',
            '-H', 'Cookie=session=abc==',
        ])
        kwargs_params = fake_sdk.credentials.add.call_args.args[4]
        assert kwargs_params['headers'] == {'Cookie': 'session=abc=='}

    def test_webauth_rejects_bad_header_format(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'add', 'credential', 'webauth',
            '-k', '#webapplication#https://app.example.com',
            '-l', 'Bad',
            '-H', 'no-equals-sign',
        ])
        assert result.exit_code != 0
        assert 'key=value' in result.output

    def test_webauth_requires_at_least_one_header(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'add', 'credential', 'webauth',
            '-k', '#webapplication#https://app.example.com',
            '-l', 'No headers',
        ])
        assert result.exit_code != 0
        assert '-H' in result.output or '--header' in result.output


class TestDeleteCredential:
    def test_delete_credential_generic_calls_sdk(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'delete', 'credential', 'generic', 'cred-abc-123',
            '-r', '#asset#example.com#1.2.3.4',
            '-t', 'active-directory',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.delete.assert_called_once_with(
            'cred-abc-123',
            '#asset#example.com#1.2.3.4',
            'active-directory',
        )

    def test_delete_credential_webauth_bakes_in_type(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'delete', 'credential', 'webauth', 'cred-abc-123',
            '-k', '#webapplication#https://app.example.com',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.delete.assert_called_once_with(
            'cred-abc-123',
            '#webapplication#https://app.example.com',
            'web-auth',
        )


class TestGetCredentialCLI:
    """`guard get credential ...` — verifies the --resolution flag and its
    interaction with CREDENTIAL_ID / --resource-key."""

    def test_default_resolution_is_by_target(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential', 'cred-abc-123',
            '--category', 'env-integration',
            '--type', 'aws',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.get.assert_called_once_with(
            'cred-abc-123', 'env-integration', 'aws', ['token'],
            resolution='by-target', resource_key=None,
        )

    def test_explicit_by_target_passes_through(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential', 'cred-abc-123',
            '--resolution', 'by-target',
            '--type', 'aws',
        ])
        assert result.exit_code == 0, result.output
        kwargs = fake_sdk.credentials.get.call_args.kwargs
        assert kwargs['resolution'] == 'by-target'
        assert kwargs['resource_key'] is None

    def test_from_parent_requires_resource_key(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential',
            '--resolution', 'from-parent',
            '--type', 'aws',
        ])
        assert result.exit_code != 0
        assert '--resource-key' in result.output
        fake_sdk.credentials.get.assert_not_called()

    def test_from_parent_with_resource_key(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential',
            '--resolution', 'from-parent',
            '--resource-key', '#asset#example.com#1.2.3.4',
            '--type', 'aws',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.credentials.get.assert_called_once_with(
            '', 'env-integration', 'aws', ['token'],
            resolution='from-parent',
            resource_key='#asset#example.com#1.2.3.4',
        )

    def test_by_target_requires_credential_id(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential',
            '--resolution', 'by-target',
            '--type', 'aws',
        ])
        assert result.exit_code != 0
        assert 'CREDENTIAL_ID' in result.output
        fake_sdk.credentials.get.assert_not_called()

    def test_invalid_resolution_value_is_rejected(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'get', 'credential', 'cred-abc-123',
            '--resolution', 'nope',
        ])
        assert result.exit_code != 0
        assert 'nope' in result.output or "'by-target'" in result.output


class TestUpdateAssetSecret:
    def test_update_asset_with_secret_passes_through(self, runner, fake_sdk):
        result = _invoke(runner, fake_sdk, [
            'update', 'asset', '#webapplication#https://app.example.com',
            '--secret', 'cred-abc-123',
        ])
        assert result.exit_code == 0, result.output
        fake_sdk.assets.update.assert_called_once_with(
            '#webapplication#https://app.example.com',
            None,         # status
            '',           # surface (default)
            secret='cred-abc-123',
        )
