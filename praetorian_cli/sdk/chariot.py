import json

import requests

from praetorian_cli.sdk.entities.accounts import Accounts
from praetorian_cli.sdk.entities.agents import Agents
from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.sdk.entities.attributes import Attributes
from praetorian_cli.sdk.entities.definitions import Definitions
from praetorian_cli.sdk.entities.files import Files
from praetorian_cli.sdk.entities.integrations import Integrations
from praetorian_cli.sdk.entities.jobs import Jobs
from praetorian_cli.sdk.entities.preseeds import Preseeds
from praetorian_cli.sdk.entities.risks import Risks
from praetorian_cli.sdk.entities.search import GLOBAL_FLAG, Search, Query
from praetorian_cli.sdk.entities.seeds import Seeds
from praetorian_cli.sdk.entities.statistics import Statistics
from praetorian_cli.sdk.entities.webhook import Webhook
from praetorian_cli.sdk.keychain import Keychain


class Chariot:

    def __init__(self, keychain: Keychain):
        self.keychain = keychain
        self.assets = Assets(self)
        self.seeds = Seeds(self)
        self.preseeds = Preseeds(self)
        self.risks = Risks(self)
        self.accounts = Accounts(self)
        self.integrations = Integrations(self)
        self.jobs = Jobs(self)
        self.files = Files(self)
        self.definitions = Definitions(self)
        self.attributes = Attributes(self)
        self.search = Search(self)
        self.webhook = Webhook(self)
        self.statistics = Statistics(self)
        self.agents = Agents(self)

    def my(self, params: dict, pages=1) -> {}:
        final_resp = dict()
        for _ in range(pages):
            resp = requests.get(self.url('/my'), params=params, headers=self.keychain.headers())
            process_failure(resp)
            resp = resp.json()
            extend(final_resp, resp)
            if 'offset' in resp:
                params['offset'] = json.dumps(resp['offset'])
            else:
                break

        if 'offset' in resp:
            final_resp['offset'] = json.dumps(resp['offset'])

        return final_resp

    def my_by_query(self, query: Query, pages=1) -> {}:
        final_resp = dict()
        for _ in range(pages):
            resp = requests.post(self.url('/my'), json=query.to_dict(), headers=self.keychain.headers())
            process_failure(resp)
            resp = resp.json()
            extend(final_resp, resp)
            if 'offset' in resp:
                query.page = int(resp['offset'])
            else:
                break

        if 'offset' in resp:
            final_resp['offset'] = resp['offset']

        return final_resp

    def post(self, type: str, body: dict, params: dict = {}):
        resp = requests.post(self.url(f'/{type}'), json=body, params=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def put(self, type: str, body: dict, params: dict = {}) -> {}:
        resp = requests.put(self.url(f'/{type}'), json=body, params=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def delete(self, type: str, body: dict, params: dict) -> {}:
        resp = requests.delete(self.url(f'/{type}'), json=body, params=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def delete_by_key(self, type: str, key: str, body: dict = {}, params: dict = {}) -> {}:
        self.delete(type, body | dict(key=key), params)

    def add(self, type: str, body: dict, params: dict = {}) -> {}:
        return self.upsert(type, body, params)

    def force_add(self, type: str, body: dict, params: dict = {}) -> {}:
        return self.post(type, body, params)

    def update(self, type: str, body: dict, params: dict = {}) -> {}:
        return self.upsert(type, body, params)

    def upsert(self, type: str, body: dict, params: dict = {}) -> {}:
        return self.put(type, body, params)

    def link_account(self, username: str, value: str = '', config: dict = {}):
        resp = requests.post(self.url(f'/account/{username}'), json=dict(config=config, value=value),
                             headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def unlink(self, username: str, value: str = '', config: dict = {}):
        resp = requests.delete(self.url(f'/account/{username}'), headers=self.keychain.headers(),
                               json=dict(value=value, config=config))
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
        presigned_url = requests.put(self.url('/file'), params=dict(name=chariot_filepath),
                                     headers=self.keychain.headers())
        process_failure(presigned_url)
        resp = requests.put(presigned_url.json()['url'], data=content)
        process_failure(resp)
        return resp

    def download(self, name: str, global_=False) -> bytes:
        params = dict(name=name)
        if global_:
            params |= GLOBAL_FLAG

        resp = requests.get(self.url('/file'), params=params, allow_redirects=True, headers=self.keychain.headers())
        process_failure(resp)
        return resp.content

    def count(self, params: dict) -> {}:
        resp = requests.get(self.url('/my/count'), params=params, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def enrichment(self, type: str, id: str):
        filename = f'{id}.json' if type == 'cve' else id
        return json.loads(self.download(f'enrichments/{type}/{filename}', True).decode('utf-8'))

    def purge(self):
        requests.delete(self.url('/account/purge'), headers=self.keychain.headers())

    def agent(self, agent: str, body: dict):
        body = body | dict(agent=agent)
        resp = requests.put(self.url('/agent'), json=body, headers=self.keychain.headers())
        process_failure(resp)
        return resp.json()

    def url(self, path: str):
        return self.keychain.base_url() + path


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
