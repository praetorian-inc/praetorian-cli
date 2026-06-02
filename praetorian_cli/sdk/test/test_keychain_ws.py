"""Tests for the optional websocket_url() accessor on Keychain."""
import pytest

from praetorian_cli.sdk.keychain import DEFAULT_PROFILE, Keychain

# Minimal keychain INI content with just the required fields (api + client_id)
MINIMAL_PROFILE = f"""
[{DEFAULT_PROFILE}]
api = https://example.com/chariot
client_id = test-client-id
username = testuser
password = testpassword
"""

PROFILE_WITH_WS = f"""
[{DEFAULT_PROFILE}]
api = https://example.com/chariot
client_id = test-client-id
username = testuser
password = testpassword
websocket = wss://example.com/ws
"""


class TestWebsocketUrl:

    def _make_keychain(self, ini_data):
        """Construct a Keychain using in-memory INI data so no real file is needed."""
        return Keychain(profile=DEFAULT_PROFILE, data=ini_data)

    def test_websocket_url_returns_none_when_unset(self, monkeypatch):
        """websocket_url() should return None (or '') when neither profile option nor env var is set."""
        monkeypatch.delenv('PRAETORIAN_CLI_WS_URL', raising=False)
        kc = self._make_keychain(MINIMAL_PROFILE)
        result = kc.websocket_url()
        assert result is None or result == '', (
            f"Expected None or '' when websocket is unset, got {result!r}"
        )

    def test_websocket_url_returns_env_var(self, monkeypatch):
        """PRAETORIAN_CLI_WS_URL env var overrides the profile option."""
        monkeypatch.setenv('PRAETORIAN_CLI_WS_URL', 'wss://env.example.com/ws')
        kc = self._make_keychain(MINIMAL_PROFILE)
        assert kc.websocket_url() == 'wss://env.example.com/ws'

    def test_websocket_url_returns_profile_option(self, monkeypatch):
        """websocket_url() returns the profile 'websocket' value when no env var override."""
        monkeypatch.delenv('PRAETORIAN_CLI_WS_URL', raising=False)
        kc = self._make_keychain(PROFILE_WITH_WS)
        assert kc.websocket_url() == 'wss://example.com/ws'

    def test_websocket_url_env_overrides_profile(self, monkeypatch):
        """Env var takes precedence over the profile 'websocket' value."""
        monkeypatch.setenv('PRAETORIAN_CLI_WS_URL', 'wss://override.example.com/ws')
        kc = self._make_keychain(PROFILE_WITH_WS)
        assert kc.websocket_url() == 'wss://override.example.com/ws'
