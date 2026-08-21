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


def test_failed_configure_write_preserves_existing_keychain(keychain_path, monkeypatch):
    """The O_TRUNC regression: writing the final path directly would zero the
    existing keychain before the new content lands, so a failure mid-write
    destroys the operator's credentials. The atomic tmp-file + os.replace path
    must leave the old keychain byte-identical when the swap fails, and must
    not litter the directory with the temp file."""
    Keychain.configure(None, None, api_key_id='kid', api_key_secret='ksecret')
    original = keychain_path.read_bytes()

    def broken_replace(src, dst):
        raise OSError('simulated')

    monkeypatch.setattr(keychain_module.os, 'replace', broken_replace)
    with pytest.raises(OSError):
        Keychain.configure('someone@example.com', 'hunter2', profile='Other')
    assert keychain_path.read_bytes() == original
    assert list(keychain_path.parent.glob('.keychain.*.tmp')) == []


@posix_modes
def test_configure_replaces_symlinked_keychain_instead_of_following_it(
        keychain_path, permissive_umask):
    """A symlink planted at the keychain path must not trick configure into
    writing credentials wherever the link points; os.replace swaps the link
    out for a regular owner-only file and leaves the target untouched."""
    keychain_path.parent.mkdir(parents=True)
    target = keychain_path.parent.parent / 'symlink-target.ini'
    target_content = '[Other]\napi = https://other.example.com\nclient_id = other\n'
    target.write_text(target_content)
    keychain_path.symlink_to(target)

    Keychain.configure(None, None, api_key_id='kid', api_key_secret='ksecret')

    assert not keychain_path.is_symlink()
    assert keychain_path.is_file()
    assert target.read_text() == target_content
    assert _mode(keychain_path) == 0o600


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


def test_token_sends_api_key_with_redirects_disabled(monkeypatch):
    """requests preserves the custom API-key headers across redirects, so the
    token request must not follow one off the validated HTTPS URL."""
    calls = []

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {'token': 'x'}

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response()

    monkeypatch.setattr(keychain_module.requests, 'get', record)
    keychain = Keychain(data=_profile(
        extra='api_key_id = kid\napi_key_secret = ksecret\n'))
    assert keychain.token() == 'x'
    assert len(calls) == 1
    assert calls[0][1]['allow_redirects'] is False


# The Cognito username/password branch: aws_endpoint_url points initiate_auth
# (which carries the password) at a local emulator, so it is a third injection
# point for a plaintext endpoint alongside the keychain api field and
# PRAETORIAN_CLI_API.


def _cognito_profile(aws_endpoint_url=None):
    extra = 'username = user\npassword = secret\n'
    if aws_endpoint_url:
        extra += f'aws_endpoint_url = {aws_endpoint_url}\n'
    return _profile(extra=extra)


def _record_boto3_client(monkeypatch):
    """Replace boto3.client with a recorder returning a stub Cognito client."""
    calls = []

    class _StubCognito:
        @staticmethod
        def initiate_auth(**kwargs):
            return {'AuthenticationResult': {'ExpiresIn': 3600, 'IdToken': 't'}}

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return _StubCognito()

    monkeypatch.setattr(keychain_module.boto3, 'client', record)
    return calls


def test_cognito_emulator_endpoint_rejected_without_opt_in(monkeypatch):
    calls = _record_boto3_client(monkeypatch)
    keychain = Keychain(data=_cognito_profile('http://localhost:4566'))
    with pytest.raises(ConfigurationError):
        keychain.token()
    assert calls == []


def test_opt_in_allows_loopback_cognito_emulator(monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, '1')
    calls = _record_boto3_client(monkeypatch)
    keychain = Keychain(data=_cognito_profile('http://localhost:4566'))
    assert keychain.token() == 't'
    assert len(calls) == 1
    assert calls[0][1]['endpoint_url'] == 'http://localhost:4566'


def test_opt_in_never_allows_non_loopback_cognito_emulator(monkeypatch):
    """Same policy as base_url(): the opt-in admits loopback only, so a
    plaintext emulator URL on a real network stays rejected even when set."""
    monkeypatch.setenv(OPT_IN_ENV, '1')
    calls = _record_boto3_client(monkeypatch)
    keychain = Keychain(data=_cognito_profile('http://198.51.100.7:4566'))
    with pytest.raises(ConfigurationError):
        keychain.token()
    assert calls == []


def test_absent_aws_endpoint_url_still_means_real_aws(monkeypatch):
    """Unset must keep meaning real AWS: the validation of a configured
    emulator URL must not turn None into a rejected or mangled endpoint."""
    calls = _record_boto3_client(monkeypatch)
    keychain = Keychain(data=_cognito_profile())
    assert keychain.token() == 't'
    assert len(calls) == 1
    assert calls[0][1]['endpoint_url'] is None
