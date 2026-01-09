import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

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


def bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes."""
    return bytes_value / (1024 * 1024)


class Chariot:

    MULTIPART_MIN_PART_SIZE = 5 * 1024 * 1024   # 5MB minimum (S3 requirement)
    MULTIPART_MAX_PARTS = 100                    # Target max parts for efficiency
    PARALLEL_UPLOADS = 4                         # Conservative to avoid connection resets
    UPLOAD_RETRY_ATTEMPTS = 3                    # Retry transient network errors

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

    # Multipart upload methods

    def _create_multipart_session(self, chariot_filepath: str) -> str:
        """Create a multipart upload session and return the upload ID."""
        print('  Creating upload session...', end='', flush=True)
        resp = self.chariot_request('POST', self.url('/file/multipart/create'), params={'name': chariot_filepath})
        process_failure(resp)
        print(' OK')
        return resp.json()['uploadId']

    def _calculate_part_size(self, file_size: int) -> int:
        """Calculate optimal part size based on file size.

        Aims for ~100 parts max for efficiency while respecting S3's 5MB minimum.
        """
        # Calculate part size to get roughly MULTIPART_MAX_PARTS parts
        target_part_size = file_size // self.MULTIPART_MAX_PARTS
        # Round up to nearest MB for cleaner chunks
        target_part_size = ((target_part_size // (1024 * 1024)) + 1) * (1024 * 1024)
        # Ensure we meet the minimum
        return max(target_part_size, self.MULTIPART_MIN_PART_SIZE)

    def _read_file_chunks(self, content, part_size: int) -> list:
        """Read file into memory as list of (part_number, chunk) tuples."""
        part_size_mb = bytes_to_mb(part_size)
        print(f'  Reading file into memory ({part_size_mb:.0f}MB parts)...', end='', flush=True)
        chunks = []
        part_number = 1
        while True:
            chunk = content.read(part_size)
            if not chunk:
                break
            chunks.append((part_number, chunk))
            part_number += 1
        print(f' OK ({len(chunks)} parts)')
        return chunks

    def _get_part_upload_url(self, chariot_filepath: str, upload_id: str, part_num: int) -> str:
        """Get presigned URL for uploading a specific part."""
        resp = self.chariot_request(
            'GET',
            self.url('/file/multipart/part'),
            params={'name': chariot_filepath, 'uploadId': upload_id, 'partNumber': str(part_num)}
        )
        process_failure(resp)
        return resp.json()['url']

    def _prefetch_upload_urls(self, chariot_filepath: str, upload_id: str, part_count: int) -> dict:
        """Pre-fetch all presigned URLs in parallel before starting uploads."""
        print(f'  Pre-fetching {part_count} upload URLs...', end='', flush=True)
        urls = {}

        def fetch_url(part_num: int):
            url = self._get_part_upload_url(chariot_filepath, upload_id, part_num)
            urls[part_num] = url

        with ThreadPoolExecutor(max_workers=self.PARALLEL_UPLOADS) as executor:
            futures = {executor.submit(fetch_url, part_num): part_num for part_num in range(1, part_count + 1)}
            for future in as_completed(futures):
                part_num = futures[future]
                try:
                    future.result()
                except Exception as e:
                    raise Exception(f'Failed to get URL for part {part_num}: {e}')

        print(' OK')
        return urls

    def _print_progress(self, state: dict, file_size: int, file_size_mb: float):
        """Print upload progress to console."""
        bytes_done = state['bytes_uploaded']
        parts_done = len(state['completed_parts'])
        total_parts = state['total_parts']
        elapsed = time.time() - state['start_time']

        progress_pct = (bytes_done / file_size) * 100 if file_size > 0 else 0
        mb_done = bytes_to_mb(bytes_done)

        # Speed based on completed bytes only (accurate)
        speed = bytes_to_mb(bytes_done) / elapsed if elapsed > 0 else 0

        print(f"\r  Progress: {mb_done:.1f}/{file_size_mb:.1f}MB ({progress_pct:.0f}%) [{parts_done}/{total_parts} parts] - {speed:.1f} MB/s    ", end='', flush=True)

    def _execute_parallel_uploads(self, chunks: list, upload_fn: callable):
        """Execute uploads in parallel using thread pool."""
        with ThreadPoolExecutor(max_workers=self.PARALLEL_UPLOADS) as executor:
            futures = {executor.submit(upload_fn, part_num, chunk): part_num for part_num, chunk in chunks}
            for future in as_completed(futures):
                part_num = futures[future]
                try:
                    future.result()
                except Exception as e:
                    raise Exception(f'Part {part_num} failed: {e}')

    def _complete_multipart_upload(self, chariot_filepath: str, upload_id: str, parts: list) -> dict:
        """Complete the multipart upload."""
        print('  Finalizing upload...', end='', flush=True)
        resp = self.chariot_request(
            'POST',
            self.url('/file/multipart/complete'),
            json={'name': chariot_filepath, 'uploadId': upload_id, 'parts': parts}
        )
        process_failure(resp)
        print(' Done.')
        return resp

    def _abort_multipart_upload(self, chariot_filepath: str, upload_id: str):
        """Abort and clean up a failed multipart upload."""
        print('  Cleaning up incomplete upload...', end='', flush=True)
        try:
            self.chariot_request(
                'POST',
                self.url('/file/multipart/abort'),
                json={'name': chariot_filepath, 'uploadId': upload_id}
            )
            print(' Done.')
        except Exception:
            print(' Failed (orphaned parts may remain).')

    def upload_multipart(self, chariot_filepath: str, content) -> dict:
        """Upload a file using multipart upload with parallel uploads and real-time progress tracking."""
        upload_id = None
        try:
            # Get file size first to calculate optimal part size
            content.seek(0, 2)  # Seek to end
            file_size = content.tell()
            content.seek(0)    # Seek back to start
            file_size_mb = bytes_to_mb(file_size)

            if file_size == 0:
                raise Exception('File is empty, cannot upload')

            part_size = self._calculate_part_size(file_size)
            upload_id = self._create_multipart_session(chariot_filepath)
            chunks = self._read_file_chunks(content, part_size)

            # Pre-fetch all presigned URLs in parallel (avoids per-part API latency)
            presigned_urls = self._prefetch_upload_urls(chariot_filepath, upload_id, len(chunks))

            print(f'  Uploading {len(chunks)} parts ({file_size_mb:.1f}MB)...')

            # Thread-safe state for parallel uploads
            state = {
                'completed_parts': {},
                'bytes_uploaded': 0,
                'total_parts': len(chunks),
                'start_time': time.time(),
            }
            state_lock = threading.Lock()

            def upload_part(part_num: int, chunk: bytes):
                """Upload a single part with retry logic."""
                chunk_size = len(chunk)
                url = presigned_urls[part_num]
                last_error = None

                for attempt in range(self.UPLOAD_RETRY_ATTEMPTS):
                    try:
                        resp = requests.put(url, data=chunk, headers={'Content-Length': str(chunk_size)})
                        process_failure(resp)

                        etag = resp.headers.get('ETag', '').strip('"')

                        with state_lock:
                            state['completed_parts'][part_num] = {'partNumber': part_num, 'etag': etag}
                            state['bytes_uploaded'] += chunk_size
                            self._print_progress(state, file_size, file_size_mb)
                        return  # Success

                    except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
                        last_error = e
                        if attempt < self.UPLOAD_RETRY_ATTEMPTS - 1:
                            time.sleep(1 * (attempt + 1))  # Backoff: 1s, 2s
                        continue

                raise Exception(f'Part {part_num} failed after {self.UPLOAD_RETRY_ATTEMPTS} attempts: {last_error}')

            self._execute_parallel_uploads(chunks, upload_part)

            print()  # New line after progress
            parts_list = [state['completed_parts'][pn] for pn in sorted(state['completed_parts'].keys())]

            total_time = time.time() - state['start_time']
            avg_speed = file_size_mb / total_time if total_time > 0 else 0
            result = self._complete_multipart_upload(chariot_filepath, upload_id, parts_list)
            print(f'  Completed in {total_time:.1f}s (avg {avg_speed:.1f} MB/s)')
            return result

        except Exception as e:
            if upload_id:
                self._abort_multipart_upload(chariot_filepath, upload_id)
            raise Exception(f'Multipart upload failed: {e}')

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
