"""Unit tests for keychain.principal_email() and decode_jwt_payload().

These tests cover the API-key auth bug: under API-key auth, the keychain
'username' field is not populated, so any helper that read it returned None.
principal_email() falls back to the JWT email claim in that case.
"""

import base64
import json

import pytest

from praetorian_cli.sdk.keychain import Keychain, decode_jwt_payload


def make_jwt(claims):
    """Build a minimal JWT-shaped string with the given payload claims.
    Signature is not verified by decode_jwt_payload, so any value works."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b'=').decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    return f"{header}.{payload}.sig"


def keychain_from_ini(ini_body):
    """Build a Keychain backed by an in-memory INI string (no file I/O)."""
    return Keychain(profile="Test", data=ini_body)


CONFIGURED_USERNAME_INI = """\
[Test]
name = chariot
client_id = test-client
api = https://example.test
username = alice@configured.example
password = sekret
"""

API_KEY_ONLY_INI = """\
[Test]
name = chariot
client_id = test-client
api = https://example.test
api_key_id = test-id
api_key_secret = test-secret
"""

EMPTY_PROFILE_INI = """\
[Test]
name = chariot
client_id = test-client
api = https://example.test
"""


class TestDecodeJwtPayload:
    def test_returns_claims_for_valid_jwt(self):
        token = make_jwt({"email": "user@customer.example", "sub": "abc"})
        assert decode_jwt_payload(token) == {"email": "user@customer.example", "sub": "abc"}

    def test_returns_none_for_non_jwt(self):
        assert decode_jwt_payload("not-a-jwt") is None
        assert decode_jwt_payload("only.two") is None

    def test_returns_none_for_garbage_payload(self):
        assert decode_jwt_payload("aaa.!!!.bbb") is None

    def test_handles_payloads_with_any_length_modulo_four(self):
        # Make sure the padding fix works for all four residues.
        # The previous chariot.py decoder added 4 '=' when len % 4 == 0,
        # which over-pads. principal_email() depends on this being robust
        # across token sizes, so test all four.
        for filler in ("", "a", "aa", "aaa"):
            token = make_jwt({"email": f"user{filler}@x.example"})
            assert decode_jwt_payload(token)["email"] == f"user{filler}@x.example"


class TestPrincipalEmail:
    def test_prefers_configured_username(self):
        kc = keychain_from_ini(CONFIGURED_USERNAME_INI)
        assert kc.principal_email() == "alice@configured.example"

    def test_falls_back_to_jwt_under_api_key_auth(self, monkeypatch):
        kc = keychain_from_ini(API_KEY_ONLY_INI)
        # Don't make a real HTTP call -- pretend the /token endpoint
        # already issued us a JWT with the owner's email.
        token = make_jwt({"email": "fox-admin@fox.example", "sub": "u-1"})
        monkeypatch.setattr(kc, "token", lambda: token)
        assert kc.principal_email() == "fox-admin@fox.example"

    def test_does_not_call_token_when_username_configured(self, monkeypatch):
        # Configured username must short-circuit -- we should never hit
        # the network just to resolve the principal.
        kc = keychain_from_ini(CONFIGURED_USERNAME_INI)
        def boom():
            raise AssertionError("token() must not be called when username is configured")
        monkeypatch.setattr(kc, "token", boom)
        assert kc.principal_email() == "alice@configured.example"

    def test_returns_none_when_no_creds(self):
        kc = keychain_from_ini(EMPTY_PROFILE_INI)
        # No username, no API key -- nothing to resolve.
        assert kc.principal_email() is None

    def test_returns_none_when_jwt_lacks_email(self, monkeypatch):
        kc = keychain_from_ini(API_KEY_ONLY_INI)
        token = make_jwt({"sub": "u-1"})  # no email claim
        monkeypatch.setattr(kc, "token", lambda: token)
        assert kc.principal_email() is None
