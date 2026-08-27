class MockConsole:
    def __init__(self):
        self.lines = []

    def print(self, msg=""):
        self.lines.append(str(msg))


class _MockAegisApi:
    """Minimal mock for aegis.api (the Chariot instance) to satisfy get_current_user()."""
    def get_current_user(self):
        return ('testuser@example.com', 'testuser')


class MockAegis:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}
        self.api = _MockAegisApi()

    def ssh_to_agent(self, agent, options, user, display_info=True):
        self.calls.append({
            'method': 'ssh_to_agent',
            'agent': agent,
            'options': list(options),
            'user': user,
            'display_info': display_info,
        })

    def copy_to_agent(self, agent, local_path, remote_path, direction='upload',
                      user=None, ssh_options=None, display_info=True, use_rsync=True):
        self.calls.append({
            'method': 'copy_to_agent',
            'agent': agent,
            'local_path': local_path,
            'remote_path': remote_path,
            'direction': direction,
            'user': user,
            'ssh_options': ssh_options or [],
            'display_info': display_info,
            'use_rsync': use_rsync,
        })
        return 0

    def run_job(self, agent, capabilities=None, config=None):
        self.calls.append({
            'method': 'run_job',
            'agent': agent,
            'capabilities': capabilities,
            'config': config,
        })
        if capabilities is None:
            return self._responses.get('list_caps', {'capabilities': []})
        return self._responses.get('run', {'success': True, 'job_id': 'abc123', 'job_key': 'k', 'status': 'queued'})

    # Newer TUI code uses these helpers
    def validate_capability(self, name):
        caps = self._responses.get('capabilities', {
            'windows-smb': {'name': 'windows-smb', 'description': 'Windows SMB capability', 'target': 'asset'},
            'linux-enum': {'name': 'linux-enum', 'description': 'Linux enum capability', 'target': 'asset'},
        })
        return caps.get(name)

    def create_job_config(self, agent, credentials=None, **kwargs):
        # Return provided credentials or an empty config as JSON-ready dict
        return credentials or self._responses.get('config', {})

    def get_available_ad_domains(self):
        return self._responses.get('domains', ['example.local'])

    def inspect_enrollment(self, user_code):
        self.calls.append({
            'method': 'inspect_enrollment',
            'user_code': user_code,
        })
        error = (self._responses.get('enrollment_errors') or {}).get('inspect')
        if error:
            raise error
        return self._responses.get('pending_enrollment', {
            'endpoint_id': 'endpoint-1',
            'account': 'customer@example.test',
            'kind': 'aegis',
            'version': '1.2.3',
            'hostname': 'sensor-1',
            'os': 'linux',
            'arch': 'amd64',
            'created_at': '2026-08-25T16:00:00Z',
            'expires_at': '2026-08-25T16:10:00Z',
        })

    def approve_enrollment(self, user_code):
        self.calls.append({
            'method': 'approve_enrollment',
            'user_code': user_code,
        })
        error = (self._responses.get('enrollment_errors') or {}).get('approve')
        if error:
            raise error
        return self._responses.get('approved_enrollment', {'status': 'approved'})

    def create_cloudflare_tunnel(self, endpoint_id):
        self.calls.append({
            'method': 'create_cloudflare_tunnel',
            'endpoint_id': endpoint_id,
        })
        error = (self._responses.get('tunnel_errors') or {}).get('create')
        if error:
            raise error
        return self._responses.get('created_tunnel', {
            'installTaskId': 'task-create',
            'hostname': 'endpoint.example.com',
            'tunnelInfo': {'tunnelName': 'endpoint-tunnel'},
            'message': 'created',
        })

    def remove_cloudflare_tunnel(self, endpoint_id):
        self.calls.append({
            'method': 'remove_cloudflare_tunnel',
            'endpoint_id': endpoint_id,
        })
        error = (self._responses.get('tunnel_errors') or {}).get('remove')
        if error:
            raise error
        return self._responses.get('removed_tunnel', {
            'taskId': 'task-remove',
            'message': 'removed',
        })

    def add_system_user(self, endpoint_id, username):
        self.calls.append({
            'method': 'add_system_user',
            'endpoint_id': endpoint_id,
            'username': username,
        })
        error = (self._responses.get('user_errors') or {}).get('add')
        if error:
            raise error
        return self._responses.get('added_user', {
            'taskId': 'task-add-user',
            'status': 'AMT_RUNNING',
            'message': 'queued',
        })

    def remove_system_user(self, endpoint_id, username, remove_home=False):
        self.calls.append({
            'method': 'remove_system_user',
            'endpoint_id': endpoint_id,
            'username': username,
            'remove_home': remove_home,
        })
        error = (self._responses.get('user_errors') or {}).get('remove')
        if error:
            raise error
        return self._responses.get('removed_user', {
            'taskId': 'task-remove-user',
            'status': 'AMT_RUNNING',
            'message': 'queued',
        })


class MockCredentials:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def list(self, offset=None, pages=100000):
        self.calls.append({
            'method': 'list',
            'offset': offset,
            'pages': pages,
        })
        # Return (credentials, next_page_token)
        credentials = self._responses.get('credentials', [])
        return credentials, None

    def get(self, credential_id, category, type, format, **parameters):
        self.calls.append({
            'method': 'get',
            'credential_id': credential_id,
            'category': category,
            'type': type,
            'format': format,
            'parameters': parameters,
        })
        # Return credential values for the specified credential
        return self._responses.get('credential_values', {
            'credentialValueEnv': {
                'USERNAME': 'testuser',
                'PASSWORD': 'testpass',
                'DOMAIN': 'example.local'
            }
        })


class MockCapabilities:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def list(self, name='', target='', executor='', surface='', endpoint_kind=''):
        self.calls.append({
            'method': 'list',
            'name': name,
            'target': target,
            'executor': executor,
            'surface': surface,
            'endpoint_kind': endpoint_kind,
        })
        caps = self._capabilities_for_scope(executor, endpoint_kind)
        if name:
            caps = [cap for cap in caps if name.lower() in cap.get('name', '').lower()]
        if target:
            caps = [cap for cap in caps if target.lower() in _capability_targets(cap)]
        if surface:
            caps = [cap for cap in caps if cap.get('surface', '').lower() == surface.lower()]
        return caps, None

    def _capabilities_for_scope(self, executor, endpoint_kind):
        if endpoint_kind:
            return list(self._responses.get('endpoint_capabilities', []))
        if 'capabilities_list' in self._responses:
            return list(self._responses.get('capabilities_list', []))
        capabilities = self._responses.get('capabilities', [])
        if isinstance(capabilities, dict):
            return list(capabilities.values())
        return list(capabilities or [])


def _capability_targets(capability):
    target = capability.get('target', [])
    if isinstance(target, list):
        return [str(item).lower() for item in target]
    return [str(target).lower()]


class MockAssets:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def add(self, group, identifier, type='asset', status='A', surface='', resource_type=''):
        self.calls.append({
            'method': 'add',
            'group': group,
            'identifier': identifier,
            'type': type,
            'status': status,
            'surface': surface,
            'resource_type': resource_type,
        })
        return self._responses.get('asset', {
            'key': f'#asset#{group}#{identifier}',
            'dns': group,
            'name': identifier,
            'type': type,
            'status': status,
        })

    def get(self, key, details=False):
        self.calls.append({
            'method': 'get',
            'key': key,
            'details': details,
        })
        assets_by_key = self._responses.get('assets_by_key', {})
        if key in assets_by_key:
            return assets_by_key[key]
        asset = self._responses.get('asset')
        if asset and asset.get('key') == key:
            return asset
        return None

    def list(self, key_prefix='', asset_type='', pages=100000):
        self.calls.append({
            'method': 'list',
            'key_prefix': key_prefix,
            'asset_type': asset_type,
            'pages': pages,
        })
        # Return (assets, next_page_token)
        assets = self._responses.get('assets', [])
        return assets, None


class MockSDK:
    def __init__(self, responses=None):
        self.aegis = MockAegis(responses=responses)
        self.jobs = MockJobs(responses=responses)
        self.credentials = MockCredentials(responses=responses)
        self.capabilities = MockCapabilities(responses=responses)
        self.assets = MockAssets(responses=responses)


class MockJobs:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def add(self, target_key, capabilities, config_json, credentials=None):
        self.calls.append({
            'method': 'add',
            'target_key': target_key,
            'capabilities': capabilities,
            'config': config_json,
            'credentials': credentials,
        })
        # Return a minimal job-like record the UI expects
        return [self._responses.get('job', {
            'key': 'jobs#abc123deadbeef',
            'status': 'queued',
        })]

    def list(self, prefix_filter='', offset=None, pages=100000):
        self.calls.append({
            'method': 'list',
            'prefix_filter': prefix_filter,
            'offset': offset,
            'pages': pages,
        })
        # Return (jobs, next_page_token)
        jobs = self._responses.get('jobs', [])
        return jobs, None


class MockCloudflaredStatus:
    def __init__(self, hostname='cf.example.com', tunnel_name='tunnel-1', authorized_users=''):
        self.hostname = hostname
        self.tunnel_name = tunnel_name
        self.authorized_users = authorized_users


class MockHealthCheck:
    def __init__(self, cf_status=None):
        self.cloudflared_status = cf_status or MockCloudflaredStatus()


class MockAgent:
    def __init__(self, hostname="agent01", client_id="C.1"):
        # Basic identity
        self.hostname = hostname
        self.client_id = client_id
        # System info (optional in UI)
        self.os = None
        self.os_version = None
        self.architecture = None
        self.fqdn = None
        # Activity/timestamps
        self.last_seen_at = 0
        # Networking
        self.network_interfaces = []
        # Tunnel/health
        self.has_tunnel = True
        self.health_check = MockHealthCheck()

    def to_detailed_string(self):
        return f"Agent {self.hostname} ({self.client_id})"


class MockMenuBase:
    def __init__(self):
        self.console = MockConsole()
        self.paused = False
        # Defaults used by newer TUI commands.
        self.multi_account_mode = False
        self.selected_accounts = []
        self.agent_account_map = {}
        self.schedule_account_map = {}
        # Minimal color map used by the UI (optional)
        self.colors = {
            'primary': 'cyan',
            'accent': 'magenta',
            'dim': 'dim',
            'success': 'green',
            'warning': 'yellow',
            'error': 'red',
            'info': 'blue',
        }

    def pause(self):
        self.paused = True

    def clear_screen(self):
        # No-op for tests; add a blank line like the real UI would
        self.console.print()
