import json
import os

import requests

from praetorian_cli.sdk.entities.accounts import Accounts
from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.sdk.entities.attributes import Attributes
from praetorian_cli.sdk.entities.definitions import Definitions
from praetorian_cli.sdk.entities.files import Files
from praetorian_cli.sdk.entities.integrations import Integrations
from praetorian_cli.sdk.entities.jobs import Jobs
from praetorian_cli.sdk.entities.risks import Risks
from praetorian_cli.sdk.entities.search import Search
from praetorian_cli.sdk.entities.seeds import Seeds
from praetorian_cli.sdk.entities.webhook import Webhook
from praetorian_cli.sdk.keychain import Keychain


class Chariot:

    def __init__(self, keychain: Keychain):
        self.keychain = keychain
        self.assets = Assets(self)
        self.seeds = Seeds(self)
        self.risks = Risks(self)
        self.accounts = Accounts(self)
        self.integrations = Integrations(self)
        self.jobs = Jobs(self)
        self.files = Files(self)
        self.definitions = Definitions(self)
        self.attributes = Attributes(self)
        self.search = Search(self)
        self.webhook = Webhook(self)

    def my(self, params: dict, pages=1) -> {}:
        final_resp = dict()
        for _ in range(pages):
            resp = requests.get(f'{self.keychain.base_url()}/my',
                                params=params, headers=self.keychain.headers())
            process_failure(resp)
            resp = resp.json()
            extend(final_resp, resp)

            if 'offset' not in resp:
                break

            params['offset'] = json.dumps(resp['offset'])

        return final_resp

    def post(self, type: str, params):
        resp = requests.post(f'{self.keychain.base_url()}/{type}',
                             json=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def put(self, type: str, params: dict) -> {}:
        resp = requests.put(f'{self.keychain.base_url()}/{type}',
                            json=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def delete(self, type: str, key: str, params: dict = {}) -> {}:
        resp = requests.delete(f'{self.keychain.base_url()}/{type}', json=dict(key=key) | params,
                               headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def add(self, type: str, params: dict) -> {}:
        return self.upsert(type, params)

    def force_add(self, type: str, params: dict) -> {}:
        return self.post(type, params)

    def update(self, type: str, params: dict) -> {}:
        return self.upsert(type, params)

    def upsert(self, type: str, params: dict) -> {}:
        return self.put(type, params)

    def link_account(self, username: str, value: str = '', config: dict = {}):
        resp = requests.post(f'{self.keychain.base_url()}/account/{username}', json=dict(config=config, value=value),
                             headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def unlink(self, username: str, value: str = ''):
        resp = requests.delete(f'{self.keychain.base_url()}/account/{username}', headers=self.keychain.headers(),
                               json={'value': value})
        process_failure(resp)
        return resp.json()

    def upload(self, local_filepath: str, chariot_filepath: str = None):
        if not chariot_filepath:
            chariot_filepath = local_filepath
        with open(local_filepath, 'rb') as content:
            resp = self._upload(chariot_filepath, content)
        return resp

    def _upload(self, chariot_filepath: str, content: str):
        # It is a two-step upload. The PUT request to the /file endpoint is to get a presigned URL for S3.
        # There is no data transfer.
        presigned_url = requests.put(f'{self.keychain.base_url()}/file', params=dict(name=chariot_filepath),
                                     headers=self.keychain.headers())
        process_failure(presigned_url)
        resp = requests.put(presigned_url.json()['url'], data=content)
        process_failure(resp)
        return resp

    def download(self, name: str, download_directory: str = ''):
        resp = requests.get(f'{self.keychain.base_url()}/file', params=dict(name=name), allow_redirects=True,
                            headers=self.keychain.headers())
        process_failure(resp)
        if not download_directory:
            return resp.content.decode('utf-8')

        name = self.sanitize_filename(name)
        directory = os.path.expanduser(download_directory)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        download_path = os.path.join(directory, name)
        with open(download_path, 'wb') as file:
            file.write(resp.content)
        return download_path

    def sanitize_filename(self, filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def count(self, params: dict) -> {}:
        resp = requests.get(f'{self.keychain.base_url()}/my/count',
                            params=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def purge(self):
        requests.delete(f'{self.keychain.base_url()}/account/purge', headers=self.keychain.headers())


def process_failure(response):
    if not response.ok:
        message = f'[{response.status_code}] Request failed' + (f'\nError: {response.text}' if response.text else '')
        raise Exception(message)


def extend(accumulate, new):
    for key, value in new.items():
        if isinstance(value, list):
            if key in accumulate:
                accumulate[key].extend(value)
            else:
                accumulate[key] = value
        elif isinstance(value, dict):
            if key not in accumulate:
                accumulate[key] = dict()
            extend(accumulate[key], value)

    return accumulate
