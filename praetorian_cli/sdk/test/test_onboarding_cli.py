"""Unit tests for onboarding CLI commands."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.onboarding  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.onboarding.cloud_initialize.return_value = {'status': 'initialized'}
    sdk.onboarding.get_customer_domains.return_value = ['example.com']
    sdk.onboarding.set_customer_domains.return_value = {'status': 'ok'}
    sdk.onboarding.verify_host_overrides.return_value = {'valid': True}
    sdk.onboarding.get_scim_settings.return_value = {'scim_managed': False}
    sdk.onboarding.set_scim_settings.return_value = {'status': 'ok'}
    return sdk


def _invoke(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


def test_cloud_init(runner, fake_sdk):
    stdin = '{"account_id": "123456789012"}'
    result = _invoke(runner, fake_sdk, [
        'onboarding', 'cloud-init', '--provider', 'aws', '--deployment-type', 'cloudformation',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    call_args = fake_sdk.onboarding.cloud_initialize.call_args[0][0]
    assert call_args['provider'] == 'aws'
    assert call_args['deployment_type'] == 'cloudformation'
    assert call_args['account_id'] == '123456789012'


def test_get_domains(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['onboarding', 'get-domains'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.onboarding.get_customer_domains.assert_called_once()


def test_set_domains(runner, fake_sdk):
    stdin = '["example.com", "test.com"]'
    result = _invoke(runner, fake_sdk, ['onboarding', 'set-domains'], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.onboarding.set_customer_domains.assert_called_once_with(['example.com', 'test.com'])


def test_verify_host_overrides(runner, fake_sdk):
    stdin = '{"host1.example.com": "10.0.0.1"}'
    result = _invoke(runner, fake_sdk, [
        'onboarding', 'verify-host-overrides',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.onboarding.verify_host_overrides.assert_called_once_with({'host1.example.com': '10.0.0.1'})


def test_get_scim_settings(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['onboarding', 'get-scim-settings'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.onboarding.get_scim_settings.assert_called_once()


def test_set_scim_settings(runner, fake_sdk):
    stdin = '{"scim_managed": true, "default_scim_role": "readonly"}'
    result = _invoke(runner, fake_sdk, [
        'onboarding', 'set-scim-settings',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.onboarding.set_scim_settings.assert_called_once_with({
        'scim_managed': True, 'default_scim_role': 'readonly',
    })
