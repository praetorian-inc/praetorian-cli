import stat
from unittest.mock import MagicMock

from praetorian_cli.sdk import keychain as keychain_module
from praetorian_cli.sdk.keychain import Keychain, TOKEN_CACHE_FILENAME


def test_token_cache_is_persisted_until_refresh_window(tmp_path, monkeypatch):
    for name in (
        'PRAETORIAN_CLI_USERNAME',
        'PRAETORIAN_CLI_PASSWORD',
        'PRAETORIAN_CLI_API_KEY_ID',
        'PRAETORIAN_CLI_API_KEY_SECRET',
        'PRAETORIAN_CLI_API',
        'PRAETORIAN_CLI_CLIENT_ID',
    ):
        monkeypatch.delenv(name, raising=False)

    keychain_path = tmp_path / 'keychain.ini'
    keychain_path.write_text(
        '[United States]\n'
        'api = https://example.test\n'
        'client_id = client-id\n'
        'api_key_id = key-id\n'
        'api_key_secret = key-secret\n'
    )

    now = {'value': 1000}
    monkeypatch.setattr(keychain_module, 'time', lambda: now['value'])

    first_response = MagicMock(status_code=200)
    first_response.json.return_value = {'IdToken': 'first-token'}
    second_response = MagicMock(status_code=200)
    second_response.json.return_value = {'IdToken': 'second-token'}
    authenticate = MagicMock(side_effect=[first_response, second_response])
    monkeypatch.setattr(keychain_module.requests, 'get', authenticate)

    assert Keychain(filepath=keychain_path).token() == 'first-token'

    now['value'] = 4299
    assert Keychain(filepath=keychain_path).token() == 'first-token'
    assert authenticate.call_count == 1

    now['value'] = 4300
    assert Keychain(filepath=keychain_path).token() == 'second-token'
    assert authenticate.call_count == 2

    cache_path = tmp_path / TOKEN_CACHE_FILENAME
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600
    assert 'key-secret' not in cache_path.read_text()
