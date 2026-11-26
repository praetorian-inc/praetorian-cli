"""Offline tests for the hosted-MCP header helper; reuse the real keychain."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.agent import mcp
from praetorian_cli.sdk import keychain as keychain_module
from praetorian_cli.sdk.keychain import Keychain


@pytest.fixture
def configured_keychain(tmp_path, monkeypatch):
    for name in ('USERNAME', 'PASSWORD', 'API_KEY_ID', 'API_KEY_SECRET', 'API', 'CLIENT_ID'):
        monkeypatch.delenv('PRAETORIAN_CLI_' + name, raising=False)
    monkeypatch.setenv('PRAETORIAN_CLI_DISABLE_UPDATE_CHECK', '1')
    path = tmp_path / 'keychain.ini'
    path.write_text(
        '[MCP]\napi = https://guard.example.test\nclient_id = client\n'
        'api_key_id = existing-id\napi_key_secret = existing-secret\n'
        'account = company@example.test\n'
    )
    return lambda **kwargs: Keychain(profile='MCP', filepath=path, **kwargs)


def invoke(keychain):
    return CliRunner().invoke(mcp, ['headers'], obj=SimpleNamespace(keychain=keychain))


def test_headers_reuse_existing_exchange_cache_and_renewal(configured_keychain, monkeypatch):
    now = [1000]
    monkeypatch.setattr(keychain_module, 'time', lambda: now[0])
    exchange = Mock(side_effect=[
        Mock(status_code=200, json=lambda: {'IdToken': 'first-token'}),
        Mock(status_code=200, json=lambda: {'IdToken': 'second-token'}),
    ])
    monkeypatch.setattr(keychain_module.requests, 'get', exchange)

    for timestamp, token in [(1000, 'first-token'), (4299, 'first-token'), (4300, 'second-token')]:
        now[0] = timestamp
        result = invoke(configured_keychain())
        assert result.exit_code == 0, result.output
        assert result.stderr == ''
        assert json.loads(result.stdout) == {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'account': 'company@example.test',
        }
        assert 'existing-secret' not in result.output
    assert exchange.call_count == 2
    assert exchange.call_args.kwargs['headers'] == {
        'X-GUARD-API-KEY-ID': 'existing-id',
        'X-GUARD-API-KEY-SECRET': 'existing-secret',
    }
    assert exchange.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('field', ['api_key_id', 'api_key_secret', 'account'])
def test_headers_require_key_and_explicit_account(configured_keychain, monkeypatch, field):
    keychain = configured_keychain().load()
    keychain.config.remove_option('MCP', field)
    if field == 'account':
        keychain.account = None
    exchange = Mock(side_effect=AssertionError('must not authenticate'))
    monkeypatch.setattr(keychain_module.requests, 'get', exchange)
    monkeypatch.setattr(keychain_module.boto3, 'client', exchange)
    result = invoke(keychain)
    assert result.exit_code != 0
    assert result.stdout == ''
    assert 'API-key profile and an explicit account' in result.stderr
    exchange.assert_not_called()


def test_headers_honor_account_override(configured_keychain, monkeypatch):
    monkeypatch.setattr(keychain_module.requests, 'get', Mock(return_value=Mock(
        status_code=200, json=lambda: {'IdToken': 'token'})))
    result = invoke(configured_keychain(account='selected@example.test'))
    assert result.exit_code == 0
    assert json.loads(result.stdout)['account'] == 'selected@example.test'


@pytest.mark.parametrize('failure', [
    Mock(status_code=401, text='credential=do-not-print'),
    RuntimeError('request headers contain do-not-print'),
])
def test_headers_fail_without_leaking_authentication_errors(configured_keychain, monkeypatch, failure):
    exchange = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    monkeypatch.setattr(keychain_module.requests, 'get', exchange)
    result = invoke(configured_keychain())
    assert result.exit_code != 0
    assert result.stdout == ''
    assert 'Unable to obtain Guard MCP headers' in result.stderr
    assert 'do-not-print' not in result.output


@pytest.mark.parametrize('command', ['guard', 'praetorian'])
def test_public_command_routing(configured_keychain, monkeypatch, command):
    import praetorian_cli.main as main_module

    monkeypatch.setattr(main_module, 'Keychain', lambda profile, account: configured_keychain(account=account))
    monkeypatch.setattr(main_module.praetorian_cli.handlers.script, 'load_dynamic_commands', lambda: None)
    monkeypatch.setattr(keychain_module.requests, 'get', Mock(return_value=Mock(
        status_code=200, json=lambda: {'IdToken': 'token'})))
    root = main_module.guard_main if command == 'guard' else main_module.main
    args = ['--profile', 'MCP', '--account', 'override@example.test']
    if command == 'praetorian':
        args.append('chariot')
    result = CliRunner().invoke(root, args + ['agent', 'mcp', 'headers'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)['account'] == 'override@example.test'


def test_headers_fail_without_leaking_malformed_profile(configured_keychain):
    keychain = configured_keychain()
    keychain.filepath.write_text('api_key_secret=do-not-print\n')
    result = invoke(keychain)
    assert result.exit_code != 0
    assert result.stdout == ''
    assert 'do-not-print' not in result.output
