import os
import tempfile
from configparser import ConfigParser
from ipaddress import ip_address
from os import environ
from os.path import join
from pathlib import Path
from time import time
from urllib.parse import urlsplit

import boto3
import requests

from praetorian_cli.sdk.exceptions import AuthenticationError, ConfigurationError
from praetorian_cli.sdk.model.globals import DEFAULT_HTTP_TIMEOUT

DEFAULT_API = 'https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot'
DEFAULT_CLIENT_ID = '795dnnr45so7m17cppta0b295o'
DEFAULT_PROFILE = 'United States'
DEFAULT_KEYCHAIN_FILEPATH = join(Path.home(), '.praetorian', 'keychain.ini')

API_KEY_ID = 'api_key_id'
API_KEY_SECRET = 'api_key_secret'

HTTP_LOOPBACK_OPT_IN_ENV = 'PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK'


def _is_loopback_host(hostname):
    """ True for localhost or a loopback IP address (127.0.0.0/8, ::1). """
    if not hostname:
        return False
    if hostname.lower() == 'localhost':
        return True
    # DNS names other than localhost (e.g. localhost.example.com) resolve to
    # arbitrary addresses, so only a literal loopback IP counts.
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validated_backend_url(api):
    """ Return `api` unchanged when it is safe to send credentials to; raise otherwise.
        HTTPS only, except plaintext HTTP to a loopback endpoint (the local dev
        emulator) under the explicit opt-in. """
    try:
        parsed = urlsplit(api or '')
        # urlsplit defers port parsing; touching .port is what raises on a URL
        # like https://host:not-a-port/x.
        parsed.port
    except ValueError:
        raise ConfigurationError(
            f'Invalid backend URL "{api}". Credentials are only sent over HTTPS; use an https:// URL.')

    if parsed.scheme == 'https' and parsed.hostname:
        return api

    if parsed.scheme == 'http' and _is_loopback_host(parsed.hostname):
        if environ.get(HTTP_LOOPBACK_OPT_IN_ENV) == '1':
            return api
        raise ConfigurationError(
            f'Refusing to send credentials to the plaintext HTTP backend "{api}". Credentials are only '
            f'sent over HTTPS. For local development against a loopback endpoint, set {HTTP_LOOPBACK_OPT_IN_ENV}=1.')

    raise ConfigurationError(
        f'Invalid backend URL "{api}". Credentials are only sent over HTTPS; use an https:// URL.')


def _tighten_to_owner_only(path):
    """ Repair a keychain file written group- or world-accessible by an older CLI. """
    # Best-effort: the file is being read, not written, and configure() remains
    # the authoritative enforcement point, so a keychain on a filesystem that
    # refuses chmod must not brick every CLI command.
    try:
        if os.stat(path).st_mode & 0o077:
            os.chmod(path, 0o600)
    except OSError:
        pass


class Keychain:

    def __init__(self, profile=DEFAULT_PROFILE, account=None, data=None, filepath=DEFAULT_KEYCHAIN_FILEPATH):
        self.profile = profile
        self.account = account
        self.data = data
        self.filepath = filepath
        self.config = None
        self._loaded = False
        self.token_cache = None
        self.token_expiry = 0

    def headers(self):
        """ Get the authentication and assume-role headers for backend requests """
        headers = {'Authorization': f'Bearer {self.load().token()}', 'Content-Type': 'application/json'}
        if self.account:
            headers['account'] = self.account

        return headers

    def load(self):
        """ Loads backend and authentication data from the keychain file into this instance. """
        # Gate on a load that finished, not on `self.config`: the parser is
        # assigned below before any validation, and an empty ConfigParser is
        # truthy (len 1 -- the DEFAULT section always counts, even with no
        # sections), so testing it would cache a half-validated parser forever
        # and never reread a keychain file the operator has since repaired.
        if self._loaded:
            return self

        self.config = ConfigParser()
        if self.data:
            self.config.read_string(self.data)
        else:
            keychain_file = Path(self.filepath)
            if not keychain_file.is_file() or not keychain_file.exists():
                # use the Production defaults
                self.config.add_section(DEFAULT_PROFILE)
                self.config.set(DEFAULT_PROFILE, 'api', DEFAULT_API)
                self.config.set(DEFAULT_PROFILE, 'client_id', DEFAULT_CLIENT_ID)
            else:
                _tighten_to_owner_only(self.filepath)
                self.config.read(self.filepath)

        if not self.config.sections():
            raise ConfigurationError(
                f'Keychain file is corrupted. Run "praetorian configure" to configure your profile and credentials. Or, delete the corrupted keychain file at {self.filepath}')

        if self.profile not in self.config:
            raise ConfigurationError(
                f'Could not find the "{self.profile}" profile in {self.filepath}. Run "praetorian configure" to fix.')

        profile = self.config[self.profile]
        
        self.load_env('username', 'PRAETORIAN_CLI_USERNAME', required=False)
        self.load_env('password', 'PRAETORIAN_CLI_PASSWORD', required=False)
        self.load_env(API_KEY_ID, 'PRAETORIAN_CLI_API_KEY_ID', required=False)
        self.load_env(API_KEY_SECRET, 'PRAETORIAN_CLI_API_KEY_SECRET', required=False)
        self.load_env('api', 'PRAETORIAN_CLI_API', required=False)
        self.load_env('client_id', 'PRAETORIAN_CLI_CLIENT_ID', required=False)
        self.load_env('websocket', 'PRAETORIAN_CLI_WS_URL', required=False)
        
        if 'api' not in profile or 'client_id' not in profile:
            raise ConfigurationError(
                f'Keychain profile "{self.profile}" is corrupted or incomplete. Run "praetorian configure" to fix.')

        if self.account is None:
            self.account = self.config.get(self.profile, 'account', fallback=None)

        self._loaded = True
        return self

    def load_env(self, config_name, env_name, required=True):
        if env_name in environ:
            # environment variable takes precedence
            self.config.set(self.profile, config_name, environ[env_name])
        elif required and not self.config.get(self.profile, config_name, fallback=None):
            # The message below instructs a repair, so this instance must be able
            # to see one: invalidate the cached load instead of answering from it.
            self._loaded = False
            raise ConfigurationError(
                f'{config_name} not in keychain file or the {env_name} environment variable. Run "praetorian configure" to fix. Or set the environment variable.')

    def token(self):
        """ Authenticate using API key or AWS Cognito and get the token. Cache the token until expiry. """
        if not self.token_cache or time() >= (self.token_expiry - 10):
            if self.has_api_key():
                # requests preserves custom headers across redirects (only the
                # standard Authorization header is stripped), so following a
                # redirect off the validated HTTPS URL could leak the key
                # headers. With redirects disabled, a redirect response lands
                # in the fail-closed status_code check below.
                response = requests.get(
                    f"{self.base_url()}/token",
                    headers={
                        'X-GUARD-API-KEY-ID': self.api_key_id(),
                        'X-GUARD-API-KEY-SECRET': self.api_key_secret(),
                    },
                    allow_redirects=False,
                    timeout=DEFAULT_HTTP_TIMEOUT,
                )
                if response.status_code != 200:
                    raise AuthenticationError(f"API key authentication failed: {response.text}")
                
                token_data = response.json()
                self.token_expiry = time() + 3600
                self.token_cache = token_data.get('token') or token_data.get('IdToken')
            else:
                # aws_endpoint_url points Cognito at a local emulator (Floci/
                # LocalStack) for local dev; None (unset) uses real AWS.
                # USER_PASSWORD_AUTH is an unsigned Cognito operation, so no AWS
                # credentials are needed for either endpoint.
                aws_endpoint_url = self.get_option('aws_endpoint_url')
                if aws_endpoint_url is not None:
                    # Same transport policy as base_url(): initiate_auth below
                    # sends the password, which must not cross plaintext HTTP.
                    aws_endpoint_url = _validated_backend_url(aws_endpoint_url)
                cognito = boto3.client('cognito-idp', region_name='us-east-2',
                                       endpoint_url=aws_endpoint_url)
                response = cognito.initiate_auth(
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters=dict(USERNAME=self.username(), PASSWORD=self.password()),
                    ClientId=self.client_id())
                self.token_expiry = time() + response['AuthenticationResult']['ExpiresIn']
                self.token_cache = response['AuthenticationResult']['IdToken']
        return self.token_cache

    def base_url(self):
        """ Get the base URL for the backend. It is the "api" field in the keychain file. """
        return _validated_backend_url(self.get_option('api'))

    def websocket_url(self):
        """ Get the optional WebSocket endpoint URL (profile 'websocket' option or PRAETORIAN_CLI_WS_URL env). Returns None if unset. """
        try:
            return self.get_option('websocket')
        except Exception:
            return None

    def username(self):
        """ Get the username field from the keychain profile """
        return self.get_option('username')

    def password(self):
        """ Get the password field from the keychain profile """
        return self.get_option('password')

    def client_id(self):
        """ Get the client_id field from the keychain profile """
        return self.get_option('client_id')

    def api_key_id(self):
        """ Get the api_key_id field from the keychain profile """
        return self.get_option(API_KEY_ID)

    def api_key_secret(self):
        """ Get the api_key field from the keychain profile """
        return self.get_option(API_KEY_SECRET)

    def has_api_key(self):
        """ Check if API key credentials are available """
        return bool(self.api_key_id() and self.api_key_secret())

    def get_option(self, option_name):
        return self.load().config.get(self.profile, option_name, fallback=None)

    def assume_role(self, account):
        """ Assume into another account """
        self.account = account

    def unassume_role(self):
        """ Resume using the sign-in account as the principal """
        self.account = None

    @staticmethod
    def configure(username, password, profile=DEFAULT_PROFILE, api=DEFAULT_API, client_id=DEFAULT_CLIENT_ID,
                  account=None, api_key_id=None, api_key_secret=None):
        """ Update or insert a new profile to the keychain file at the default location.
            If the keychain file does not exist, create it. """
        # Reject a plaintext backend before the keychain file is created or modified.
        _validated_backend_url(api)

        new_profile = {
            'name': 'chariot',
            'client_id': client_id,
            'api': api
        }

        if username:
            new_profile['username'] = username

        if password:
            new_profile['password'] = password

        if account:
            new_profile['account'] = account

        if api_key_id:
            new_profile[API_KEY_ID] = api_key_id

        if api_key_secret:
            new_profile[API_KEY_SECRET] = api_key_secret

        config = ConfigParser()
        config.read(DEFAULT_KEYCHAIN_FILEPATH)

        config[profile] = new_profile

        keychain_dir = Path(DEFAULT_KEYCHAIN_FILEPATH).parent
        # mkdir's mode leaves a pre-existing directory alone; a new one is created
        # owner-only to match the file it holds.
        keychain_dir.mkdir(mode=0o700, exist_ok=True, parents=True)
        # Write to a same-directory temp file (mkstemp creates it 0600 at the open
        # syscall, regardless of umask) and atomically replace the keychain: a
        # failure at any point leaves an existing keychain intact rather than
        # truncated, and os.replace swaps out a symlink planted at the final path
        # instead of following it.
        fd, tmp_path = tempfile.mkstemp(dir=keychain_dir, prefix='.keychain.', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                config.write(f)
                f.flush()
                os.fsync(fd)
            os.replace(tmp_path, DEFAULT_KEYCHAIN_FILEPATH)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise
