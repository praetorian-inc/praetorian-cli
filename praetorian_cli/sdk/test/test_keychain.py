"""Keychain storage-permission and backend-URL scheme tests (ENG-6636).

Two properties, both purely local (no backend access):

1. At rest: the keychain file holding passwords / API keys is created with
   owner-only permissions, and a pre-existing file written looser by an older
   CLI is tightened whenever the keychain is written or read.
2. In transit: credentials are only ever sent to an HTTPS backend. A plaintext
   ``http://`` backend is rejected before any request is made; the sole
   exception is a loopback endpoint (the local Cognito/LocalStack dev flow)
   under the explicit ``PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK=1`` opt-in.
"""

import os
import stat
import sys
from configparser import ConfigParser

import pytest

import praetorian_cli.sdk.keychain as keychain_module
from praetorian_cli.sdk.exceptions import ConfigurationError
from praetorian_cli.sdk.keychain import Keychain

# The documented opt-in interface. A literal on purpose: renaming the variable
# in keychain.py must fail these tests, since the old name is what operators
# have in their dev environments.
OPT_IN_ENV = 'PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK'

posix_modes = pytest.mark.skipif(
    sys.platform == 'win32',
    reason='POSIX file modes; on Windows chmod is close to a no-op',
)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _profile(api='https://api.example.com/chariot', extra=''):
    return f'[United States]\napi = {api}\nclient_id = test-client-id\n{extra}'


@pytest.fixture(autouse=True)
def _clean_cli_environment(monkeypatch):
    """PRAETORIAN_CLI_* variables in the operator's real environment override
    keychain fields inside load(); strip them so tests see only their own."""
    for name in list(os.environ):
        if name.startswith('PRAETORIAN_CLI_'):
            monkeypatch.delenv(name)


@pytest.fixture
def keychain_path(tmp_path, monkeypatch):
    path = tmp_path / '.praetorian' / 'keychain.ini'
    monkeypatch.setattr(keychain_module, 'DEFAULT_KEYCHAIN_FILEPATH', str(path))
    return path


@pytest.fixture
def permissive_umask():
    previous = os.umask(0)
    yield
    os.umask(previous)


# ---------------------------------------------------------------- at rest


@posix_modes
def test_configure_creates_keychain_owner_only_under_permissive_umask(
        keychain_path, permissive_umask):
    """A plain open(path, 'w') under umask 0 would land at 0666; the mode must
    come from the code, not from whatever umask the operator happens to run."""
    Keychain.configure(None, None, api_key_id='kid', api_key_secret='ksecret')
    assert _mode(keychain_path) == 0o600


@posix_modes
def test_configure_tightens_pre_existing_world_readable_keychain(keychain_path):
    keychain_path.parent.mkdir(parents=True)
    keychain_path.write_text(_profile())
    keychain_path.chmod(0o644)
    Keychain.configure(None, None, api_key_id='kid', api_key_secret='ksecret')
    assert _mode(keychain_path) == 0o600


@posix_modes
def test_load_tightens_pre_existing_world_readable_keychain(keychain_path):
    """Existing installs have 0644 keychains from older CLI versions and may
    never re-run configure; any read of the keychain repairs the mode."""
    keychain_path.parent.mkdir(parents=True)
    keychain_path.write_text(_profile())
    keychain_path.chmod(0o644)
    Keychain(filepath=str(keychain_path)).load()
    assert _mode(keychain_path) == 0o600


def test_configure_preserves_other_profiles(keychain_path):
    keychain_path.parent.mkdir(parents=True)
    keychain_path.write_text('[Other]\napi = https://other.example.com\nclient_id = other\n')
    Keychain.configure(None, None, api_key_id='kid', api_key_secret='ksecret')
    config = ConfigParser()
    config.read(keychain_path)
    assert 'Other' in config
    assert 'United States' in config
    assert config.get('United States', 'api_key_secret') == 'ksecret'


# ------------------------------------------------------------- in transit


def test_base_url_returns_https_backend_verbatim():
    api = 'https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot'
    assert Keychain(data=_profile(api)).base_url() == api


def test_http_loopback_is_rejected_without_opt_in():
    with pytest.raises(ConfigurationError):
        Keychain(data=_profile('http://localhost:3000/chariot')).base_url()


@pytest.mark.parametrize('api', [
    'http://localhost:3000/chariot',
    'http://127.0.0.1:8010',
    'http://[::1]:9000/chariot',
])
def test_opt_in_allows_loopback_http(monkeypatch, api):
    monkeypatch.setenv(OPT_IN_ENV, '1')
    assert Keychain(data=_profile(api)).base_url() == api


@pytest.mark.parametrize('api', [
    'http://api.example.com/chariot',
    'http://192.168.1.10:8000',
    'http://localhost.example.com',
])
def test_opt_in_never_allows_non_loopback_http(monkeypatch, api):
    """The opt-in is for the local dev emulator only; a plaintext backend on a
    real network stays rejected even with the variable set."""
    monkeypatch.setenv(OPT_IN_ENV, '1')
    with pytest.raises(ConfigurationError):
        Keychain(data=_profile(api)).base_url()


@pytest.mark.parametrize('value', ['true', 'yes', '0', ''])
def test_opt_in_value_must_be_exactly_1(monkeypatch, value):
    monkeypatch.setenv(OPT_IN_ENV, value)
    with pytest.raises(ConfigurationError):
        Keychain(data=_profile('http://localhost:3000/chariot')).base_url()


@pytest.mark.parametrize('api', [
    'ftp://api.example.com/chariot',
    'api.example.com/chariot',
    'https://',
    'https://api.example.com:not-a-port/chariot',
])
def test_malformed_or_non_http_backends_are_rejected(api):
    with pytest.raises(ConfigurationError):
        Keychain(data=_profile(api)).base_url()


def test_token_never_sends_api_key_to_plaintext_backend(monkeypatch):
    """The property the ticket actually cares about: a poisoned profile must
    fail before the API-key id/secret headers leave the process."""
    calls = []
    monkeypatch.setattr(keychain_module.requests, 'get',
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    keychain = Keychain(data=_profile(
        'http://api.example.com/chariot',
        extra='api_key_id = kid\napi_key_secret = ksecret\n'))
    with pytest.raises(ConfigurationError):
        keychain.token()
    assert calls == []


def test_env_var_backend_override_is_validated(monkeypatch):
    """PRAETORIAN_CLI_API takes precedence over the keychain file, so it is a
    second injection point for a plaintext endpoint."""
    monkeypatch.setenv('PRAETORIAN_CLI_API', 'http://api.example.com/chariot')
    with pytest.raises(ConfigurationError):
        Keychain(data=_profile()).base_url()


def test_configure_rejects_plaintext_backend_before_writing(keychain_path):
    with pytest.raises(ConfigurationError):
        Keychain.configure(None, None, api='http://api.example.com/chariot',
                           api_key_id='kid', api_key_secret='ksecret')
    assert not keychain_path.exists()
