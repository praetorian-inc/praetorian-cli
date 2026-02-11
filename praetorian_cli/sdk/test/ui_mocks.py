class MockConsole:
    def __init__(self):
        self.lines = []

    def print(self, msg=""):
        self.lines.append(str(msg))


class MockAegis:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def ssh_to_agent(self, agent, options, user, display_info=True, no_record=False):
        self.calls.append({
            'method': 'ssh_to_agent',
            'agent': agent,
            'options': list(options),
            'user': user,
            'display_info': display_info,
            'no_record': no_record,
        })

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


class MockAssets:
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

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

    def list(self, prefix_filter=None):
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
        # Minimal color map used by the UI (optional)
        self.colors = {
            'primary': 'cyan',
            'accent': 'magenta',
            'dim': 'dim',
            'success': 'green',
            'warning': 'yellow',
            'error': 'red',
        }

    def pause(self):
        self.paused = True

    def clear_screen(self):
        # No-op for tests; add a blank line like the real UI would
        self.console.print()
