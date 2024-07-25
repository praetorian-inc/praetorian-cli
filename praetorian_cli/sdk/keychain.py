import configparser
import os
import time
from functools import wraps
from pathlib import Path

import boto3
import click

DEFAULT_API = 'https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot'
DEFAULT_CLIENT_ID = '795dnnr45so7m17cppta0b295o'
DEFAULT_PROFILE = "United States"


def verify_credentials(func):
    @wraps(verify_credentials)
    def handler(*args, **kwargs):
        try:
            keychain = args[0].keychain
            keychain.set_config()
            keychain.set_headers(keychain.account)
            return func(*args, **kwargs)

        except KeyError as e:
            raise Exception('Keychain missing: %s' % e)
        except StopIteration:
            raise Exception('Could not find "%s" profile in %s' % (args[0].keychain.profile, args[0].keychain.location))

    handler.__wrapped__ = func
    return handler


class Keychain:

    def __init__(self, profile=DEFAULT_PROFILE, account=None, data=None,
                 location=os.path.join(Path.home(), '.praetorian', 'keychain.ini')):
        self.profile = profile
        self.account = account
        self.location = location
        self.data = data
        self.token_cache = None
        self.token_expiry = 0

    def set_config(self):
        cfg = self.get()
        if not cfg.sections():
            exit('Keychain file is empty. Run "praetorian configure" to configure your profile and credentials.')
        try:
            self.username = cfg[self.profile]['username']
            self.password = cfg[self.profile]['password']
            self.api = cfg[self.profile]['api']
            self.client_id = cfg[self.profile]['client_id']
            if self.account is None:
                self.account = cfg.get(self.profile, 'account', fallback=None)
        except Exception as e:
            exit(
                f'Keychain profile "{self.profile}" is corrupted or incomplete. Run "praetorian configure" to fix.')

    def get(self):
        cfg = configparser.ConfigParser()

        if self.data:
            cfg.read_string(self.data)
        else:
            cfg.read(self.location)

        return cfg

    def configure(self, username, password, profile=DEFAULT_PROFILE, api=DEFAULT_API, client_id=DEFAULT_CLIENT_ID,
                  account=''):
        cfg = configparser.ConfigParser()
        cfg[profile] = {
            'name': 'chariot',
            'client_id': client_id,
            'api': api,
            'username': username,
            'password': password
        }
        if account:
            cfg[profile]['account'] = account

        combo = self._merge_configs(cfg, self.get())

        Path(os.path.split(Path(self.location))[0]).mkdir(parents=True, exist_ok=True)
        with open(self.location, 'w') as f:
            combo.write(f)

        click.echo(f'\nKeychain data written to {self.location}')

    def set_headers(self, account=None):
        self.headers = {
            'Authorization': f'Bearer {self.token()}',
            'Content-Type': 'application/json'
        }
        if account:
            self.headers['account'] = account

    def token(self):
        if not self.token_cache or time.time() >= self.token_expiry:
            response = boto3.client('cognito-idp', region_name='us-east-2').initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={'USERNAME': self.username, 'PASSWORD': self.password},
                ClientId=self.client_id
            )
            self.token_expiry = time.time() + response['AuthenticationResult']['ExpiresIn']
            self.token_cache = response['AuthenticationResult']['IdToken']
        return self.token_cache

    @staticmethod
    def _merge_configs(cfg_from, cfg_to):
        for section in cfg_from.sections():
            cfg_to[section] = cfg_from[section]
        return cfg_to
