import configparser
import os
from functools import wraps
from os.path import exists
from pathlib import Path

import boto3


def verify_credentials(func):
    @wraps(verify_credentials)
    def handler(*args, **kwargs):
        try:
            keychain = args[0].keychain
            secrets = keychain.get()

            keychain.api = secrets.get(keychain.profile, 'api')
            keychain.client_id = secrets.get(keychain.profile, 'client_id')
            keychain.username = secrets.get(keychain.profile, 'username', fallback=None)
            keychain.password = secrets.get(keychain.profile, 'password', fallback=None)
            if keychain.account is None:
                keychain.account = secrets.get(keychain.profile, 'account', fallback=None)

            if not (keychain.username and keychain.password):
                new_credentials = keychain.write_credentials()
                keychain.username = new_credentials['username']
                keychain.password = new_credentials['password']

            keychain.headers = {
                'Authorization': f'Bearer {keychain.token()}',
                'Content-Type': 'application/json'
            }
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

    def token(self):
        cognito_client = boto3.client('cognito-idp', region_name='us-east-2')
        response = cognito_client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': self.username,
                'PASSWORD': self.password
            },
            ClientId=self.client_id
        )
        return response['AuthenticationResult']['IdToken']

    @staticmethod
    def _merge_configs(cfg_from, cfg_to):
        for section in cfg_from.sections():
            if section not in cfg_to:
                cfg_to[section] = {}
            for key, value in cfg_from[section].items():
                cfg_to[section][key] = value
        return cfg_to
