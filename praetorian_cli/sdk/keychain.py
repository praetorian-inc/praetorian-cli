from configparser import ConfigParser
from os import environ
from os.path import join, split
from pathlib import Path
from time import time

import boto3
import click

from praetorian_cli.handlers.utils import error

DEFAULT_API = 'https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot'
DEFAULT_CLIENT_ID = '795dnnr45so7m17cppta0b295o'
DEFAULT_PROFILE = 'United States'
DEFAULT_USER_POOL_ID = 'us-east-2_BJ6QHVG2L'
DEFAULT_KEYCHAIN_FILEPATH = join(Path.home(), '.praetorian', 'keychain.ini')


class Keychain:

    def __init__(self, profile=DEFAULT_PROFILE, account=None, data=None, filepath=DEFAULT_KEYCHAIN_FILEPATH):
        self.profile = profile
        self.account = account
        self.data = data
        self.filepath = filepath
        self.config = None
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
        if self.config:
            return self

        self.config = ConfigParser()
        if self.data:
            self.config.read_string(self.data)
        else:
            self.config.read(self.filepath)
        if not self.config.sections():
            error('Keychain file is empty. Run "praetorian configure" to configure your profile and credentials.')

        if self.profile not in self.config:
            error(f'Could not find the "{self.profile}" profile in {self.filepath}. Run "praetorian configure" to fix.')

        profile = self.config[self.profile]
        if 'api' not in profile or 'client_id' not in profile:
            error(f'Keychain profile "{self.profile}" is corrupted or incomplete. Run "praetorian configure" to fix.')

        self.load_env('username', 'PRAETORIAN_CLI_USERNAME')
        self.load_env('password', 'PRAETORIAN_CLI_PASSWORD')

        if self.account is None:
            self.account = self.config.get(self.profile, 'account', fallback=None)

        return self

    def load_env(self, config_name, env_name):
        if not self.config.get(self.profile, config_name, fallback=None):
            if env_name in environ:
                self.config.set(self.profile, config_name, environ[env_name])
            else:
                error(
                    f'{config_name} not in keychain or the {env_name} env variable. Run "praetorian configure" to fix.')

    def token(self):
        """ Authenticate to AWS Cognito and get the token. Cache the token until expiry. """
        if not self.token_cache or time() >= (self.token_expiry - 10):
            response = boto3.client('cognito-idp', region_name='us-east-2').initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters=dict(USERNAME=self.username(), PASSWORD=self.password()),
                ClientId=self.client_id())
            self.token_expiry = time() + response['AuthenticationResult']['ExpiresIn']
            self.token_cache = response['AuthenticationResult']['IdToken']
        return self.token_cache

    def base_url(self):
        """ Get the base URL for the backend. It is the "api" field in the keychain file. """
        return self.get_option('api')

    def username(self):
        """ Get the username field from the keychain profile """
        return self.get_option('username')

    def password(self):
        """ Get the password field from the keychain profile """
        return self.get_option('password')

    def client_id(self):
        """ Get the client_id field from the keychain profile """
        return self.get_option('client_id')

    def get_option(self, option_name):
        return self.load().config.get(self.profile, option_name)

    def assume_role(self, account):
        """ Assume into another account """
        self.account = account

    def unassume_role(self):
        """ Resume using the sign-in account as the principal """
        self.account = None

    @staticmethod
    def configure(username, password, profile=DEFAULT_PROFILE, api=DEFAULT_API, client_id=DEFAULT_CLIENT_ID,
                  user_pool_id=DEFAULT_USER_POOL_ID, account=None):
        """ Update or insert a new profile to the keychain file at the default location.
            If the keychain file does not exist, create it. """
        new_profile = {
            'name': 'chariot',
            'client_id': client_id,
            'api': api,
            'user_pool_id': user_pool_id,
        }

        if username:
            new_profile['username'] = username

        if password:
            new_profile['password'] = password

        if account:
            new_profile['account'] = account

        config = ConfigParser()
        config.read(DEFAULT_KEYCHAIN_FILEPATH)

        config[profile] = new_profile

        Path(split(Path(DEFAULT_KEYCHAIN_FILEPATH))[0]).mkdir(exist_ok=True, parents=True)
        with open(DEFAULT_KEYCHAIN_FILEPATH, 'w') as f:
            config.write(f)

        click.echo(f'\nKeychain data written to {DEFAULT_KEYCHAIN_FILEPATH}')
