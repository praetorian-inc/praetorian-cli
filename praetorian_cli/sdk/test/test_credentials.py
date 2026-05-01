"""Unit tests for credential add/delete + WebApplication default-credential
('--secret') update — both at the SDK layer and through the CLI."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# Importing these for their side-effects: each handler module registers its
# Click commands on the `chariot` group via decorators at import time.
import praetorian_cli.handlers.add  # noqa: F401
import praetorian_cli.handlers.delete  # noqa: F401
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
