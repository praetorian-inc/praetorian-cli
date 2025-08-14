import json, requests

from praetorian_cli.sdk.entities.accounts import Accounts
from praetorian_cli.sdk.entities.agents import Agents
from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.sdk.entities.attributes import Attributes
from praetorian_cli.sdk.entities.capabilities import Capabilities
from praetorian_cli.sdk.entities.configurations import Configurations
from praetorian_cli.sdk.entities.credentials import Credentials
from praetorian_cli.sdk.entities.definitions import Definitions
from praetorian_cli.sdk.entities.files import Files
from praetorian_cli.sdk.entities.integrations import Integrations
from praetorian_cli.sdk.entities.jobs import Jobs
from praetorian_cli.sdk.entities.keys import Keys
from praetorian_cli.sdk.entities.preseeds import Preseeds
from praetorian_cli.sdk.entities.risks import Risks
from praetorian_cli.sdk.entities.search import Search
from praetorian_cli.sdk.entities.seeds import Seeds
from praetorian_cli.sdk.entities.settings import Settings
from praetorian_cli.sdk.entities.statistics import Statistics
from praetorian_cli.sdk.entities.webhook import Webhook
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.model.globals import GLOBAL_FLAG
from praetorian_cli.sdk.model.query import Query, my_params_to_query, DEFAULT_PAGE_SIZE
from praetorian_cli.sdk.entities.generic import Generic


class Chariot:

    def __init__(self, keychain: Keychain, proxy: str=''):
        self.keychain = keychain
        self.generic = Generic(self)
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
        self.settings = Settings(self)
        self.configurations = Configurations(self)
        self.keys = Keys(self)
        self.capabilities = Capabilities(self)
        self.credentials = Credentials(self)
        self.proxy = proxy

        if self.proxy:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Centralized method to make HTTP requests with proxy configuration.
        Automatically applies proxy settings and verify=False if proxy is defined.
        """

        if self.proxy:
            kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
            kwargs['verify'] = False

        return requests.request(method, url, headers=self.keychain.headers(), **kwargs)

    def my(self, params: dict, pages=1) -> dict:
        final_resp = dict()

        query = my_params_to_query(params)
        if query:
            # The search is on data in Neo4j, which uses NoahQL.
            return self.my_by_query(query, pages)

        # The search is on data in DynamoDB, which uses DynamoDB's native offset format.
        for _ in range(pages):
            resp = self._make_request('GET', self.url('/my'), params=params)
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

    def my_by_query(self, query: Query, pages=1) -> dict:
        return self.my_by_raw_query(query.to_dict(), pages, query.params())

    def my_by_raw_query(self, raw_query: dict, pages=1, params: dict = {}) -> dict:
        if 'page' not in raw_query:
            raw_query['page'] = 0

        if 'limit' not in raw_query:
            raw_query['limit'] = DEFAULT_PAGE_SIZE

        final_resp = dict()

        while pages > 0:
            resp = self._make_request('POST', self.url('/my'), json=raw_query, params=params)
            if is_query_limit_failure(resp):
                # In this block, the data size is too large for the number of records requested in raw_query['limit'].
                # We need to halve the page size: LIMIT = LIMIT / 2
                # But in order to still retrieve the next page of results, we now need to double the offset: OFFSET = OFFSET * 2
                # In addition, we need to double the number of remaining pages to fetch: PAGES = PAGES * 2
                raw_query['limit'] //= 2
                raw_query['page'] *= 2
                pages *= 2
                continue

            process_failure(resp)
            resp = resp.json()
            extend(final_resp, resp)

            if 'offset' in resp:
                raw_query['page'] = int(resp['offset'])
                pages -= 1
            else:
                break

        if 'offset' in resp:
            final_resp['offset'] = resp['offset']

        return final_resp

    def post(self, type: str, body: dict, params: dict = {}) -> dict:
        resp = self._make_request('POST', self.url(f'/{type}'), json=body, params=params)
        process_failure(resp)
        return resp.json()

    def put(self, type: str, body: dict, params: dict = {}) -> dict:
        resp = self._make_request('PUT', self.url(f'/{type}'), json=body, params=params)
        process_failure(resp)
        return resp.json()

    def get(self, type: str, params: dict = {}) -> dict:
        resp = self._make_request('GET', self.url(f'/{type}'), params=params)
        process_failure(resp)
        return resp.json()

    def delete(self, type: str, body: dict, params: dict) -> dict:
        resp = self._make_request('DELETE', self.url(f'/{type}'), json=body, params=params)
        process_failure(resp)
        return resp.json()

    def delete_by_key(self, type: str, key: str, body: dict = {}, params: dict = {}) -> dict:
        self.delete(type, body | dict(key=key), params)

    def add(self, type: str, body: dict, params: dict = {}) -> dict:
        return self.upsert(type, body, params)

    def force_add(self, type: str, body: dict, params: dict = {}) -> dict:
        return self.post(type, body, params)

    def update(self, type: str, body: dict, params: dict = {}) -> dict:
        return self.upsert(type, body, params)

    def upsert(self, type: str, body: dict, params: dict = {}) -> dict:
        return self.put(type, body, params)

    def link_account(self, username: str, value: str = '', config: dict = {}) -> dict:
        resp = self._make_request('POST', self.url(f'/account/{username}'), json=dict(config=config, value=value))
        process_failure(resp)
        return resp.json()

    def unlink(self, username: str, value: str = '', config: dict = {}) -> dict:
        resp = self._make_request('DELETE', self.url(f'/account/{username}'), json=dict(value=value, config=config))
        process_failure(resp)
        return resp.json()

    def upload(self, local_filepath: str, chariot_filepath: str = None) -> dict:
        if not chariot_filepath:
            chariot_filepath = local_filepath
        with open(local_filepath, 'rb') as content:
            resp = self._upload(chariot_filepath, content)
        return resp

    def _upload(self, chariot_filepath: str, content: str) -> dict:
        # It is a two-step upload. The PUT request to the /file endpoint is to get a presigned URL for S3.
        # There is no data transfer.
        presigned_url = self._make_request('PUT', self.url('/file'), params=dict(name=chariot_filepath))
        process_failure(presigned_url)
        resp = requests.put(presigned_url.json()['url'], data=content)
        process_failure(resp)
        return resp

    def download(self, name: str, global_=False) -> bytes:
        params = dict(name=name)
        if global_:
            params |= GLOBAL_FLAG

        resp = self._make_request('GET', self.url('/file'), params=params, allow_redirects=True)
        process_failure(resp)
        return resp.content

    def count(self, params: dict) -> dict:
        resp = self._make_request('GET', self.url('/my/count'), params=params)
        process_failure(resp)
        return resp.json()

    def enrichment(self, type: str, id: str) -> dict:
        filename = f'{id}.json' if type == 'cve' else id
        return json.loads(self.download(f'enrichments/{type}/{filename}', True).decode('utf-8'))

    def purge(self):
        self._make_request('DELETE', self.url('/account/purge'))

    def agent(self, agent: str, body: dict) -> dict:
        body = body | dict(agent=agent)
        resp = self._make_request('PUT', self.url('/agent'), json=body)
        process_failure(resp)
        return resp.json()

    def url(self, path: str) -> str:
        return self.keychain.base_url() + path

    def is_praetorian_user(self) -> bool:
        return self.keychain.username().endswith('@praetorian.com')

    def start_mcp_server(self, allowable_tools=None):
        """ Start MCP server exposing SDK methods as tools
        
        Arguments:
        allowable_tools: list
            Optional list of tool names to expose. If None, all tools are exposed.
            Tool names should be in format 'entity.method' (e.g., 'assets.add', 'risks.list')
        """
        from praetorian_cli.sdk.mcp_server import MCPServer
        import anyio
        
        server = MCPServer(self, allowable_tools)
        return anyio.run(server.start)
def is_query_limit_failure(response: requests.Response) -> bool:
    return response.status_code == 413 and 'reduce page size' in response.text


def process_failure(response: requests.Response):
    if not response.ok:
        message = f'[{response.status_code}] Request failed' + (f'\nError: {response.text}' if response.text else '')
        raise Exception(message)


def extend(accumulate: dict, new: dict) -> dict:
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
