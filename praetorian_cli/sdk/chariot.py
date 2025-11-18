import json, requests, os

from praetorian_cli.sdk.entities.accounts import Accounts
from praetorian_cli.sdk.entities.aegis import Aegis
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
from praetorian_cli.sdk.entities.scanners import Scanners
from praetorian_cli.sdk.entities.schema import Schema
from praetorian_cli.sdk.entities.search import Search
from praetorian_cli.sdk.entities.seeds import Seeds
from praetorian_cli.sdk.entities.settings import Settings
from praetorian_cli.sdk.entities.statistics import Statistics
from praetorian_cli.sdk.entities.webpage import Webpage
from praetorian_cli.sdk.entities.webhook import Webhook
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.model.globals import GLOBAL_FLAG
from praetorian_cli.sdk.model.query import Query, my_params_to_query, DEFAULT_PAGE_SIZE


class Chariot:

    def __init__(self, keychain: Keychain, proxy: str=''):
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
        self.scanners = Scanners(self)
        self.webhook = Webhook(self)
        self.statistics = Statistics(self)
        self.aegis = Aegis(self)
        self.agents = Agents(self)
        self.settings = Settings(self)
        self.configurations = Configurations(self)
        self.keys = Keys(self)
        self.capabilities = Capabilities(self)
        self.credentials = Credentials(self)
        self.webpage = Webpage(self)
        self.schema = Schema(self)
        self.proxy = proxy

        if self.proxy == '' and os.environ.get('CHARIOT_PROXY'):
            self.proxy = os.environ.get('CHARIOT_PROXY')

        if self.proxy:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def chariot_request(self, method: str, url: str, headers: dict = {}, **kwargs) -> requests.Response:
        """
        Centralized wrapper around requests.request. Take care of proxy, beta flag, and 
        supplies the authentication headers
        """
        self.add_beta_url_param(kwargs)

        if self.proxy:
            kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
            kwargs['verify'] = False

        return requests.request(method, url, headers=(headers | self.keychain.headers()), **kwargs)


    def add_beta_url_param(self, kwargs: dict):
        if 'params' in kwargs:
            kwargs['params']['beta'] = 'true'
        else:
            kwargs['params'] = {'beta': 'true'}

    def my(self, params: dict, pages=1) -> dict:
        final_resp = dict()

        query = my_params_to_query(params)
        if query:
            # The search is on data in Neo4j, which uses NoahQL.
            return self.my_by_query(query, pages)

        # The search is on data in DynamoDB, which uses DynamoDB's native offset format.
        for _ in range(pages):
            resp = self.chariot_request('GET', self.url('/my'), params=params)
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
            resp = self.chariot_request('POST', self.url('/my'), json=raw_query, params=params)
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
        resp = self.chariot_request('POST', self.url(f'/{type}'), json=body, params=params)
        process_failure(resp)
        return resp.json()

    def put(self, type: str, body: dict, params: dict = {}) -> dict:
        resp = self.chariot_request('PUT', self.url(f'/{type}'), json=body, params=params)
        process_failure(resp)
        return resp.json()

    def get(self, type: str, params: dict = {}) -> dict:
        resp = self.chariot_request('GET', self.url(f'/{type}'), params=params)
        process_failure(resp)
        return resp.json()

    def delete(self, type: str, body: dict, params: dict) -> dict:
        resp = self.chariot_request('DELETE', self.url(f'/{type}'), json=body, params=params)
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
        resp = self.chariot_request('POST', self.url(f'/account/{username}'), json=dict(config=config, value=value))
        process_failure(resp)
        return resp.json()

    def unlink(self, username: str, value: str = '', config: dict = {}) -> dict:
        resp = self.chariot_request('DELETE', self.url(f'/account/{username}'), json=dict(value=value, config=config))
        process_failure(resp)
        return resp.json()

    def upload(self, local_filepath: str, chariot_filepath: str = None) -> dict:
        if not chariot_filepath:
            chariot_filepath = local_filepath
        with open(local_filepath, 'rb') as content:
            resp = self._upload(chariot_filepath, content)
        return resp

    def _upload(self, chariot_filepath: str, content: str) -> dict:
        # Encrypted files have _encrypted/ prefix in the path. Encrypted files do not use presigned URLs.
        # Instead, they use the /encrypted-file endpoint that directly gets and puts content.
        if is_encrypted_partition(chariot_filepath):
            return self.chariot_request('PUT', self.url('/encrypted-file'), params=dict(name=chariot_filepath), data=content)

        # Regular files use presigned URLs
        presigned_url = self.chariot_request('PUT', self.url('/file'), params=dict(name=chariot_filepath))
        process_failure(presigned_url)
        resp = requests.put(presigned_url.json()['url'], data=content)
        process_failure(resp)
        return resp

    def download(self, name: str, global_=False) -> bytes:
        params = dict(name=name)
        # Encrypted files have _encrypted/ prefix in the path. Encrypted files do not use presigned URLs.
        # Instead, they use the /encrypted-file endpoint that directly gets and puts content.
        if is_encrypted_partition(name):
            accept_binary = {'Accept': 'application/octet-stream'}
            resp = self.chariot_request('GET', self.url('/encrypted-file'), params=params, headers=accept_binary)
            process_failure(resp)
            return resp.content

        # Regular files, use presigned URLs
        if global_:
            params |= GLOBAL_FLAG

        resp = self.chariot_request('GET', self.url('/file'), params=params)
        process_failure(resp)

        data = resp.json()
        url = data.get("url", None)
        if not url:
            message = f'Download request failed: response missing URL' + (f'\nBody: {resp.text}' if resp.text else '(empty)')
            raise Exception(message)
        
        resp = requests.request('GET', url)
        process_failure(resp)
        return resp.content

    def count(self, params: dict) -> dict:
        resp = self.chariot_request('GET', self.url('/my/count'), params=params)
        process_failure(resp)
        return resp.json()

    def enrichment(self, type: str, id: str) -> dict:
        filename = f'{id}.json' if type == 'cve' else id
        return json.loads(self.download(f'enrichments/{type}/{filename}', True).decode('utf-8'))

    def purge(self):
        self.chariot_request('DELETE', self.url('/account/purge'))

    def agent(self, agent: str, body: dict) -> dict:
        body = body | dict(agent=agent)
        resp = self.chariot_request('PUT', self.url('/agent'), json=body)
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

    def get_current_user(self) -> tuple:
        """
        Get current user information for Aegis functionality.
        
        Returns:
            tuple: (user_email, username) where user_email is the login email
                   and username is the SSH username derived from the email
        """
        # Try to get username from keychain first (for username/password auth)
        user_email = self.keychain.username()
        
        # If no username in keychain (API key auth), try to get it from JWT token
        if not user_email and self.keychain.has_api_key():
            token = self.keychain.token()
            payload = decode_jwt_payload(token)
            if payload:
                # Extract email from the 'email' field in the JWT payload
                user_email = payload.get('email')
            else:
                # If JWT decoding fails, fall back to the account parameter
                raise Exception("Failed to decode JWT token")
        
        # Extract username from email (part before @) for SSH access
        username = user_email.split('@')[0] if user_email and '@' in user_email else user_email
        return user_email, username


def decode_jwt_payload(token: str) -> dict | None:
    """
    Decode the payload from a JWT token.
    
    Args:
        token: JWT token string in format header.payload.signature
        
    Returns:
        dict: Decoded payload contents, or None if decoding fails
        
    Example:
        >>> token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6InVzZXJAZXhhbXBsZS5jb20ifQ.signature"
        >>> payload = decode_jwt_payload(token)
        >>> print(payload.get('email'))
        user@example.com
    """
    try:
        import json
        import base64
        
        # JWT tokens have 3 parts: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        payload_part = parts[1]
        # Add padding if needed for base64 decoding
        payload_part += '=' * (4 - len(payload_part) % 4)
        payload = json.loads(base64.b64decode(payload_part))
        
        return payload
    except Exception:
        return None


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


def is_encrypted_partition(chariot_filepath: str) -> bool:
    return chariot_filepath.startswith('_encrypted/')
