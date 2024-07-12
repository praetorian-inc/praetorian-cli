import configparser
import os
import time
from functools import wraps
from os.path import exists
from pathlib import Path

import boto3


def verify_credentials(func):
    @wraps(verify_credentials)
    def handler(*args, **kwargs):
        try:
            keychain = args[0].keychain
            keychain.set_config()

            if not (keychain.username and keychain.password):
                new_credentials = keychain.write_credentials()
                keychain.username = new_credentials['username']
                keychain.password = new_credentials['password']

            keychain.set_headers()
            if keychain.account:
                keychain.headers['account'] = keychain.account

            return func(*args, **kwargs)

        except KeyError as e:
            raise Exception('Keychain missing: %s' % e)
        except StopIteration:
            raise Exception('Could not find "%s" profile in %s' % (args[0].keychain.profile, args[0].keychain.location))

    handler.__wrapped__ = func
    return handler


class Keychain:

    def __init__(self, profile='United States', account=None, data=None,
                 location=os.path.join(Path.home(), '.praetorian', 'keychain.ini')):
        self.profile = profile
        self.account = account
        self.location = location
        self.data = data
        self.token_cache = None
        self.token_expiry = 0
        self.set_config()

    def set_config(self):
        cfg = self.get()
        self.username = cfg[self.profile]['username']
        self.password = cfg[self.profile]['password']
        self.api = cfg[self.profile]['api']
        self.client_id = cfg[self.profile]['client_id']
        if self.account is None:
            self.account = cfg.get(self.profile, 'account', fallback=None)

    def get(self):
        cfg = configparser.ConfigParser()

        if self.data:
            cfg.read_string(self.data)
        else:
            cfg.read(self.location)

        if not cfg.sections():
            exit(
                '[!] Follow instructions at at https://docs.praetorian.com/hc/en-us/articles/25815154096667-The'
                '-Praetorian-CLI to obtain a keychain.')
        return cfg

    def write_credentials(self):
        username = input("Enter username: ")
        password = input("Enter password: ")

        if not exists(self.location):
            head, _ = os.path.split(Path(self.location))
            Path(head).mkdir(parents=True, exist_ok=True)
            open(self.location, 'x').close()

        cfg = configparser.ConfigParser()
        cfg[self.profile] = {
            'username': username,
            'password': password
        }
        combo = self._merge_configs(cfg, self.get())
        with open(self.location, 'w') as f:
            combo.write(f)
        return {
            'username': username,
            'password': password
        }

    def set_headers(self):
        self.headers = {
            'Authorization': f'Bearer {self.token()}',
            'Content-Type': 'application/json'
        }

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
            if section not in cfg_to:
                cfg_to[section] = {}
            for key, value in cfg_from[section].items():
                cfg_to[section][key] = value
        return cfg_to
