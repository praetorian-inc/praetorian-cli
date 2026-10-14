from typing import List, Optional
import json
import logging
from urllib.parse import quote
import shlex
import shutil
import subprocess
import time
from praetorian_cli.sdk.model.aegis import Agent, is_v2_agent, validate_agent_for_ssh

def normalize_to_list(value, item_keys: List[str] = None) -> List:
    keys = item_keys or ["items", "data", "capabilities", "assets"]
    if value is None:
        return []
    if isinstance(value, tuple) and value:
        value = value[0]
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for k in keys:
            if k in value and isinstance(value[k], list):
                return value[k]
        return []
    return []


def _is_aegis_endpoint(value) -> bool:
    return isinstance(value, dict) and str(value.get('kind', '')).lower() == 'aegis'


def merge_aegis_endpoint_rows(
    identity_rows,
    live_rows,
    tunnel_rows=None,
    status_rows=None,
) -> List[dict]:
    """Merge durable identities with live status and persisted tunnel state."""
    merged = {}
    order = []

    for row in identity_rows or []:
        if not isinstance(row, dict):
            continue
        endpoint_id = _endpoint_row_id(row)
        if not endpoint_id:
            continue
        normalized = dict(row)
        normalized.setdefault('kind', 'aegis')
        if endpoint_id not in merged:
            order.append(endpoint_id)
        merged[endpoint_id] = normalized

    for row in live_rows or []:
        if not _is_aegis_endpoint(row):
            continue
        endpoint_id = _endpoint_row_id(row)
        if not endpoint_id:
            continue
        if endpoint_id not in merged:
            order.append(endpoint_id)
        merged[endpoint_id] = {**merged.get(endpoint_id, {}), **row}

    for row in tunnel_rows or []:
        if not isinstance(row, dict):
            continue
        endpoint_id = _endpoint_row_id(row)
        tunnel = row.get('cloudflaredStatus')
        if endpoint_id in merged and isinstance(tunnel, dict):
            merged[endpoint_id]['cloudflaredStatus'] = dict(tunnel)

    for row in status_rows or []:
        if not isinstance(row, dict):
            continue
        endpoint_id = _endpoint_row_id(row)
        observed = row.get('cloudflared')
        if endpoint_id not in merged or not isinstance(observed, dict):
            continue
        tunnel = merged[endpoint_id].get('cloudflaredStatus')
        if isinstance(tunnel, dict):
            continue
        if observed.get('state'):
            merged[endpoint_id]['cloudflaredStatus'] = {
                'status': observed['state'],
            }

    return [merged[endpoint_id] for endpoint_id in order]


def is_active_aegis_inventory_row(row) -> bool:
    return bool(
        _is_aegis_endpoint(row)
        and str(row.get('lifecycleState', '')).lower() != 'revoked'
    )


def normalize_active_endpoint_summary(row) -> dict:
    """Convert the /endpoint summary contract to the canonical endpoint shape."""
    return {
        'endpointId': row.get('endpoint_id'),
        'hostname': row.get('hostname'),
        'lastSeenAt': row.get('last_heartbeat'),
        'kind': 'aegis',
    }


def _endpoint_row_id(row) -> str:
    return str(row.get('endpointId') or '')


ENROLLMENT_INSPECT_PATH = 'endpoint/enrollment/inspect'
ENROLLMENT_APPROVE_PATH = 'endpoint/enrollment/approve'
ENDPOINT_NETWORK_POLICY_PATH = 'endpoint/{endpoint_id}/network-policy'
AEGIS_MANAGEMENT_TASKS_PATH = 'aegis/management/tasks'
CLOUDFLARE_TUNNEL_STATUS_PATH = 'aegis/management/cloudflare/tunnel/status/{endpoint_id}'
CLOUDFLARE_TUNNEL_CREATE_PATH = 'aegis/management/cloudflare/tunnel/create'
CLOUDFLARE_TUNNEL_REMOVE_PATH = 'aegis/management/cloudflare/tunnel/remove'
ENDPOINT_PIN_CONFIG_KEY = 'endpoint_agent_id'
# The endpoint kind that runs Aegis capabilities, mobile ones included.
ENDPOINT_KIND_AEGIS = 'aegis'
# Connection state in which an endpoint can pick up work.
ENDPOINT_STATE_ONLINE = 'online'
LINUX_SYSTEM_ADDUSER = 'linux-system-adduser'
LINUX_SYSTEM_DELUSER = 'linux-system-deluser'


def _enrollment_user_code_payload(user_code: str) -> dict:
    code = str(user_code or '').strip()
    if not code:
        raise ValueError('enrollment user code is required')
    return {'userCode': code}


def _required_endpoint_id(endpoint_id: str) -> str:
    endpoint_id = str(endpoint_id or '').strip()
    if not endpoint_id:
        raise ValueError('endpoint ID is required')
    return endpoint_id


def _required_username(username: str) -> str:
    username = str(username or '').strip()
    if not username:
        raise ValueError('username is required')
    return username


def _endpoint_tunnel_payload(agent_id: str, legacy: bool = False) -> dict:
    key = 'aegisClientId' if legacy else 'endpointAgentId'
    return {key: _required_endpoint_id(agent_id)}


def _endpoint_management_task_payload(capability: str, agent_id: str, parameters: dict = None, legacy: bool = False) -> dict:
    task_parameters = dict(parameters or {})
    payload = {
        'aegisManagementCapability': capability,
        'parameters': task_parameters,
    }
    if legacy:
        payload['aegisClientId'] = _required_endpoint_id(agent_id)
    else:
        task_parameters[ENDPOINT_PIN_CONFIG_KEY] = _required_endpoint_id(agent_id)
    return payload


def normalize_pending_enrollment(pending: dict) -> dict:
    """Return only safe enrollment review fields from an inspect response."""
    if not isinstance(pending, dict):
        return {}

    metadata = pending.get('metadata') or pending.get('Metadata') or {}
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        'endpoint_id': pending.get('endpointId') or pending.get('endpoint_id') or '',
        'account': pending.get('account') or pending.get('Account') or '',
        'kind': pending.get('kind') or pending.get('Kind') or '',
        'version': metadata.get('version') or metadata.get('Version') or '',
        'hostname': metadata.get('hostname') or metadata.get('Hostname') or '',
        'os': metadata.get('os') or metadata.get('OS') or '',
        'arch': metadata.get('arch') or metadata.get('Arch') or '',
        'created_at': pending.get('createdAt') or pending.get('created_at') or '',
        'expires_at': pending.get('expiresAt') or pending.get('expires_at') or '',
    }


class Aegis:
    """ The methods in this class are to be accessed from sdk.aegis, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api


    def list(self, *, on_warning=None) -> tuple[List[Agent], None]:
        """List legacy and v2 agents independently, returning (agents, None).

        Send partial failures to on_warning(message), or the logger if omitted.
        Raise RuntimeError if both inventories fail. A successful empty response
        still counts as a loaded inventory.
        """
        agents = []
        errors = []
        loaded = False
        try:
            agents.extend(self._list_legacy_agents())
            loaded = True
        except Exception as exc:
            errors.append(f'Legacy Aegis inventory: {exc}')
        try:
            endpoints, endpoint_errors = self._list_endpoint_agents()
            agents.extend(endpoints)
            errors.extend(endpoint_errors)
            loaded = True
        except Exception as exc:
            errors.append(f'Aegis v2 inventory: {exc}')

        if not loaded:
            raise RuntimeError('Failed to load Aegis inventories: ' + '; '.join(errors))
        if errors:
            message = 'Incomplete Aegis inventory: ' + '; '.join(errors)
            warn = on_warning if on_warning is not None else logging.getLogger(__name__).warning
            warn(message)
        return agents, None

    def _list_legacy_agents(self) -> List[Agent]:
        agents_data = self.api.get('/agent/enhanced')
        return [Agent.from_dict(agent_data) for agent_data in agents_data]

    def _list_endpoint_agents(self) -> tuple[List[Agent], List[str]]:
        errors = []
        try:
            identity_rows = self._list_endpoint_inventory_rows()
        except Exception as exc:
            errors.append(f'Aegis v2 durable inventory: {exc}')
            try:
                identity_rows = self._list_active_endpoint_rows()
            except Exception as exc:
                errors.append(f'Aegis v2 active inventory: {exc}')
                identity_rows = None

        live_rows = None
        tunnel_rows = []
        status_rows = []
        if hasattr(self.api, 'search'):
            try:
                endpoints_data, _ = self.api.search.by_key_prefix('#endpoint#')
                live_rows = normalize_to_list(
                    endpoints_data,
                    ["endpoints", "endpointInfos", "endpointinfos", "data", "items"],
                )
            except Exception as exc:
                if identity_rows is None:
                    errors.append(f'Aegis v2 live inventory: {exc}')
            try:
                tunnel_rows, _ = self.api.search.by_key_prefix(
                    '#endpointaegistunnelstate#'
                )
            except Exception:
                pass
            try:
                status_rows, _ = self.api.search.by_key_prefix(
                    '#endpointaegisstatus#'
                )
            except Exception:
                pass

        if identity_rows is None and live_rows is None:
            raise RuntimeError('; '.join(errors))
        rows = merge_aegis_endpoint_rows(
            identity_rows or [],
            live_rows or [],
            tunnel_rows,
            status_rows,
        )
        return [Agent.from_endpoint_dict(endpoint) for endpoint in rows], errors

    def list_hunt_endpoints(self) -> List[Agent]:
        """List active tenant-owned Aegis v2 identities for Internal Hunts."""
        return [
            Agent.from_endpoint_dict(endpoint)
            for endpoint in self._list_active_endpoint_rows()
        ]

    def _list_endpoint_inventory_rows(self) -> List[dict]:
        endpoints = []
        cursor = None
        seen_cursors = set()
        while True:
            params = {'cursor': cursor} if cursor else {}
            response = self.api.get('endpoint/list', params)
            rows = normalize_to_list(response, ['endpoints', 'data', 'items'])
            endpoints.extend(
                endpoint for endpoint in rows
                if is_active_aegis_inventory_row(endpoint)
            )
            cursor = response.get('cursor') if isinstance(response, dict) else None
            if not cursor:
                return endpoints
            if cursor in seen_cursors:
                raise ValueError('endpoint inventory returned a repeated cursor')
            seen_cursors.add(cursor)

    def _list_active_endpoint_rows(self) -> List[dict]:
        endpoint_data = self.api.get('endpoint')
        endpoints = normalize_to_list(endpoint_data, ['endpoints', 'data', 'items'])
        return [
            normalize_active_endpoint_summary(endpoint)
            for endpoint in endpoints
            if isinstance(endpoint, dict)
        ]

    def get_by_client_id(self, client_id: str) -> Optional[Agent]:
        """
        Get a specific Aegis agent by client ID.

        :param client_id: The unique client identifier for the agent
        :type client_id: str
        :return: Agent object if found, None if not found
        :rtype: Agent or None

        **Example Usage:**
            >>> # Get specific agent
            >>> agent = sdk.aegis.get_by_client_id("C.6e012b467f9faf82-OG9F0")
            >>> if agent:
            >>>     print(f"Found agent: {agent.hostname}")
            >>>     print(f"Tunnel status: {agent.has_tunnel}")
        """
        try:
            agents_data, _ = self.list()
            for agent in agents_data:
                if agent.display_id == client_id:
                    return agent
            return None
        except Exception as e:
            raise Exception(f"Failed to get agent {client_id}: {e}")
    
    def inspect_enrollment(self, user_code: str) -> dict:
        """Inspect safe pending Aegis v2 enrollment details for a user code."""
        response = self.api.post(ENROLLMENT_INSPECT_PATH, _enrollment_user_code_payload(user_code))
        return normalize_pending_enrollment(response)

    def approve_enrollment(self, user_code: str) -> dict:
        """Approve a pending Aegis v2 enrollment user code."""
        response = self.api.post(ENROLLMENT_APPROVE_PATH, _enrollment_user_code_payload(user_code))
        if not isinstance(response, dict):
            return {'status': 'approved'}
        return {'status': response.get('status') or response.get('Status') or 'approved'}

    def get_endpoint_network_policy(self, endpoint_id: str) -> dict:
        """Get the desired and applied host egress policy for an Aegis v2 endpoint."""
        path = ENDPOINT_NETWORK_POLICY_PATH.format(
            endpoint_id=quote(_required_endpoint_id(endpoint_id), safe=''),
        )
        return self.api.get(path)

    def update_endpoint_network_policy(
        self,
        endpoint_id: str,
        expected_revision: int,
        disabled_default_rule_ids: List[str],
        custom_deny_rules: List[dict],
    ) -> dict:
        """Replace an Aegis v2 endpoint policy using optimistic revision control."""
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError('expected network policy revision must be a non-negative integer')
        path = ENDPOINT_NETWORK_POLICY_PATH.format(
            endpoint_id=quote(_required_endpoint_id(endpoint_id), safe=''),
        )
        return self.api.put(path, {
            'expectedRevision': expected_revision,
            'disabledDefaultRuleIds': list(disabled_default_rule_ids or []),
            'customDenyRules': [dict(rule) for rule in custom_deny_rules or []],
        })

    def get_cloudflare_tunnel_status(self, endpoint_id: str) -> dict:
        """Get safe configuration and runtime health for an Aegis v2 tunnel."""
        path = CLOUDFLARE_TUNNEL_STATUS_PATH.format(
            endpoint_id=quote(_required_endpoint_id(endpoint_id), safe=''),
        )
        return self.api.get(path)

    def create_cloudflare_tunnel(self, agent_id: str, *, legacy: bool = False) -> dict:
        """Create and install a Cloudflare tunnel on a selected Aegis agent."""
        return self.api.post(CLOUDFLARE_TUNNEL_CREATE_PATH, _endpoint_tunnel_payload(agent_id, legacy))

    def remove_cloudflare_tunnel(self, agent_id: str, *, legacy: bool = False) -> dict:
        """Remove Cloudflare tunnel configuration from a selected Aegis agent."""
        return self.api.post(CLOUDFLARE_TUNNEL_REMOVE_PATH, _endpoint_tunnel_payload(agent_id, legacy))

    def add_system_user(self, agent_id: str, username: str, *, legacy: bool = False) -> dict:
        """Add a Linux user through Aegis management."""
        return self.api.post(
            AEGIS_MANAGEMENT_TASKS_PATH,
            _endpoint_management_task_payload(
                LINUX_SYSTEM_ADDUSER,
                agent_id,
                {'username': _required_username(username)},
                legacy,
            ),
        )

    def remove_system_user(self, agent_id: str, username: str, remove_home: bool = False, *, legacy: bool = False) -> dict:
        """Remove a Linux user through Aegis management."""
        remove_home_value = '--remove-home' if remove_home else ''
        return self.api.post(
            AEGIS_MANAGEMENT_TASKS_PATH,
            _endpoint_management_task_payload(
                LINUX_SYSTEM_DELUSER,
                agent_id,
                {
                    'username': _required_username(username),
                    'remove_home': remove_home_value,
                },
                legacy,
            ),
        )

    def get_capabilities(self, surface_filter: str = None, agent_os: str = None,
                         target: str = None, endpoint_kind: str = None,
                         executor: str = 'aegis') -> List[dict]:
        """
        Get Aegis capabilities with optional filtering.

        Retrieves available capabilities that can be executed by Aegis agents,
        with optional filtering by attack surface and operating system.

        :param surface_filter: Filter by attack surface type (e.g., 'internal', 'external', 'mobile')
        :type surface_filter: str or None
        :param agent_os: Filter by agent operating system (e.g., 'windows', 'linux')
        :type agent_os: str or None
        :param target: Filter by target type (e.g., 'asset', 'addomain', 'apk')
        :type target: str or None
        :param endpoint_kind: Filter to capabilities dispatchable to an enrolled endpoint of
            this kind (e.g., 'aegis')
        :type endpoint_kind: str or None
        :param executor: Filter by executor. Defaults to 'aegis', which is the executor for
            capabilities that run on an SSH-reachable Aegis agent. Endpoint-dispatched
            capabilities -- including every mobile one -- are registered against Guard's own
            executor instead, so pass '' to include them.
        :type executor: str
        :return: List of capability dictionaries
        :rtype: list

        **Example Usage:**
            >>> # Get all Aegis capabilities
            >>> caps = sdk.aegis.get_capabilities()
            
            >>> # Get internal surface capabilities only
            >>> internal_caps = sdk.aegis.get_capabilities(surface_filter='internal')
            
            >>> # Get Windows capabilities for internal surface
            >>> win_caps = sdk.aegis.get_capabilities(surface_filter='internal', agent_os='windows')

            >>> # Get the mobile capabilities dispatchable to an enrolled Android endpoint
            >>> mobile_caps = sdk.aegis.get_capabilities(target='apk', endpoint_kind='aegis', executor='')

        **Capability Object Properties:**
            Each capability contains:
            - name: Capability name (e.g., 'windows-smb-snaffler')
            - description: Human-readable description
            - target: Target type ('asset', 'addomain', etc.)
            - surface: Attack surface ('internal', 'external')
            - parameters: List of configurable parameters
        """
        try:
            capabilities_response = self.api.capabilities.list(
                target=target or '', executor=executor or '', endpoint_kind=endpoint_kind or '')
            
            # Handle different response formats
            if isinstance(capabilities_response, tuple):
                all_capabilities, _ = capabilities_response
            elif isinstance(capabilities_response, list):
                all_capabilities = capabilities_response
            elif isinstance(capabilities_response, dict):
                all_capabilities = capabilities_response.get('capabilities', 
                                                           capabilities_response.get('data', 
                                                                                   capabilities_response.get('items', [])))
            else:
                all_capabilities = []
            
            # Ensure we have a list and all items are dicts
            caps = normalize_to_list(all_capabilities, ["capabilities", "data", "items"]) or []
            caps = [c for c in caps if isinstance(c, dict)]
            
            # Apply surface filter
            if surface_filter:
                caps = [
                    cap for cap in caps 
                    if isinstance(cap, dict) and cap.get('surface', '').lower() == surface_filter.lower()
                ]
            
            # Apply OS filter
            if agent_os:
                caps = [
                    cap for cap in caps
                    if isinstance(cap, dict) and cap.get('name', '').lower().startswith(f'{agent_os.lower()}-')
                ]
            
            return caps
            
        except Exception as e:
            raise Exception(f"Failed to get Aegis capabilities: {e}")
    
    def validate_capability(self, capability_name: str) -> Optional[dict]:
        """
        Validate and get capability information by name.

        :param capability_name: Name of the capability to validate
        :type capability_name: str
        :return: Capability information if valid, None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> # Validate a capability
            >>> cap_info = sdk.aegis.validate_capability('windows-smb-snaffler')
            >>> if cap_info:
            >>>     print(f"Valid capability: {cap_info['name']}")
            >>>     print(f"Target type: {cap_info['target']}")
        """
        try:
            match = _by_name(self.get_capabilities(), capability_name)
            if match:
                return match
            # Endpoint-dispatched capabilities -- every mobile one among them -- are
            # registered against Guard's own executor, so the agent-executor list above
            # never holds them and a valid name would look invalid.
            return _by_name(self.get_capabilities(endpoint_kind=ENDPOINT_KIND_AEGIS, executor=''),
                            capability_name)
        except Exception:
            return None
    
    def create_job_config(self, agent, credentials=None):
        """
        Create job configuration for Aegis agent.

        :param agent: Agent object containing client_id and other metadata
        :type agent: Agent
        :param credentials: Optional dictionary containing Username/Password for authentication
        :type credentials: dict or None
        :return: Job configuration dictionary
        :rtype: dict

        **Example Usage:**
            >>> # Basic config without credentials
            >>> config = sdk.aegis.create_job_config(agent)
            
            >>> # Config with credentials
            >>> creds = {"Username": "admin", "Password": "secret"}
            >>> config = sdk.aegis.create_job_config(agent, creds)
        """
        if is_v2_agent(agent):
            raise Exception(
                "Aegis v2 endpoint job execution is not supported by the legacy "
                "Aegis job path; refusing to create aegis/client_id config"
            )

        config = {
            "aegis": "true",
            "client_id": agent.client_id or '',
            "manual": "true"
        }
        
        if credentials:
            config.update(credentials)
            
        return config
    
    def get_available_ad_domains(self) -> List[str]:
        """
        Get available Active Directory domains from assets.

        Retrieves all AD domain assets from the account, extracting domain names
        from both the DNS field and asset keys for comprehensive coverage.

        :return: List of available AD domain names
        :rtype: list

        **Example Usage:**
            >>> # Get all available AD domains
            >>> domains = sdk.aegis.get_available_ad_domains()
            >>> print(f"Found {len(domains)} domains: {domains}")
            
            >>> # Use for job targeting
            >>> if 'contoso.com' in domains:
            >>>     target_key = f"#addomain#contoso.com#contoso.com"

        **Domain Discovery:**
            Domains are extracted from:
            - Asset DNS field (primary method)
            - Asset key field format: #addomain#domain.com#domain.com (fallback)
        """
        domains = []
        try:
            assets_resp = self.api.assets.list(asset_type='addomain')
            
            # Handle different response formats
            if isinstance(assets_resp, tuple):
                assets, _ = assets_resp
            else:
                assets = assets_resp
            
            if isinstance(assets, dict):
                assets = assets.get('assets', assets.get('data', assets.get('items', [])))
            elif isinstance(assets, list):
                pass  # assets is already a list
            else:
                assets = []
            
            for asset in (assets or []):
                if isinstance(asset, dict):
                    dns = asset.get('dns', '')
                    key = asset.get('key', '')
                    
                    # Try DNS field first
                    if dns and dns not in domains:
                        domains.append(dns)
                    # If no DNS, try to extract from key format: #addomain#domain.com#domain.com
                    elif key and '#addomain#' in key:
                        parts = key.split('#')
                        if len(parts) >= 3 and parts[1] == 'addomain':
                            domain = parts[2]
                            if domain and domain not in domains:
                                domains.append(domain)
            
            return sorted(domains)
            
        except Exception as e:
            raise Exception(f"Failed to get available domains: {e}")
    
    def ssh_to_agent(self, agent: Agent, options: List[str] = None, user: str = None, display_info: bool = True) -> int:
        """SSH to an Aegis agent or v2 endpoint using its Cloudflare tunnel."""

        options = options or []
        
        is_valid, error_msg = validate_agent_for_ssh(agent)
        if not is_valid:
            raise Exception(error_msg)

        # Determine SSH username using the centralized method
        if not user:
            _, user = self.api.get_current_user()
        
        hostname = agent.hostname or 'Unknown'
        cf_status = agent.health_check.cloudflared_status
        public_hostname = cf_status.hostname
        authorized_users = cf_status.authorized_users or ''
        tunnel_name = cf_status.tunnel_name or 'N/A'
        
        # Check if user is authorized (if authorization is configured)
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            if user not in users_list:
                print(f"User '{user}' may not be authorized for tunnel. Authorized users: {', '.join(users_list)}")
        
        ssh_command = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
        ssh_command.extend(options)
        ssh_command.append(f'{user}@{public_hostname}')
        
        # Parse forwarding options for display (simple extraction from SSH flags)
        local_forward = []
        remote_forward = []
        dynamic_forward = []
        
        # Extract forwarding info for display
        i = 0
        while i < len(options):
            if options[i] == '-L' and i + 1 < len(options):
                local_forward.append(options[i + 1])
                i += 2
            elif options[i] == '-R' and i + 1 < len(options):
                remote_forward.append(options[i + 1])
                i += 2
            elif options[i] == '-D' and i + 1 < len(options):
                dynamic_forward.append(options[i + 1])
                i += 2
            else:
                i += 1

        if display_info:
            print(f"\033[1;36m→ Connecting to {hostname}\033[0m")
            print(f"\033[34m  Gateway: {public_hostname}\033[0m")
            print(f"\033[33m  Tunnel:  {tunnel_name}\033[0m")
            print(f"\033[35m  User:    {user}\033[0m")
            
            if local_forward:
                print(f"\033[32m  Local:   {', '.join(local_forward)}\033[0m")
            if remote_forward:
                print(f"\033[31m  Remote:  {', '.join(remote_forward)}\033[0m")
            if dynamic_forward:
                socks = ', '.join([f"localhost:{p}" for p in dynamic_forward])
                print(f"\033[35m  SOCKS:   {socks}\033[0m")
            print("")

        result = subprocess.run(ssh_command)
        return result.returncode

    def copy_to_agent(self, agent: Agent, local_path: str, remote_path: str,
                      direction: str = 'upload', user: str | None = None,
                      ssh_options: List[str] | None = None, display_info: bool = True,
                      use_rsync: bool = True) -> int:
        """Copy files to/from an Aegis agent using rsync (with scp fallback).

        :param agent: Target agent
        :param local_path: Local file or directory path
        :param remote_path: Remote file or directory path
        :param direction: 'upload' or 'download'
        :param user: SSH username (resolved from API if omitted)
        :param ssh_options: Extra SSH flags (e.g. ['-i', '~/.ssh/key'])
        :param display_info: Print connection banner
        :param use_rsync: Try rsync first; fall back to scp on failure
        :return: Process exit code
        """
        ssh_options = ssh_options or []
        if is_v2_agent(agent):
            raise Exception("Aegis v2 endpoint file copy is not supported")

        is_valid, error_msg = validate_agent_for_ssh(agent)
        if not is_valid:
            raise Exception(error_msg)

        if not user:
            _, user = self.api.get_current_user()

        hostname = agent.hostname or 'Unknown'
        cf_status = agent.health_check.cloudflared_status
        public_hostname = cf_status.hostname
        tunnel_name = cf_status.tunnel_name or 'N/A'

        remote_spec = f'{user}@{public_hostname}'

        # Build the base SSH command string for rsync's -e flag
        ssh_parts = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
        ssh_parts.extend(ssh_options)
        ssh_cmd_str = shlex.join(ssh_parts)

        if display_info:
            action = 'Upload to' if direction == 'upload' else 'Download from'
            print(f"\033[1;36m→ {action} {hostname}\033[0m")
            print(f"\033[34m  Gateway: {public_hostname}\033[0m")
            print(f"\033[33m  Tunnel:  {tunnel_name}\033[0m")
            print(f"\033[35m  User:    {user}\033[0m")
            if direction == 'upload':
                print(f"\033[32m  Local:   {local_path}\033[0m")
                print(f"\033[32m  Remote:  {remote_path}\033[0m")
            else:
                print(f"\033[32m  Remote:  {remote_path}\033[0m")
                print(f"\033[32m  Local:   {local_path}\033[0m")
            print("")

        # Try rsync first if available and requested
        rsync_path, _, _ = self._find_rsync()
        if use_rsync and rsync_path:
            cmd = self._build_rsync_command(ssh_cmd_str, local_path, remote_spec, remote_path, direction)
            t0 = time.monotonic()
            result = subprocess.run(cmd)
            elapsed = time.monotonic() - t0
            # Exit code 127 means rsync not found on the remote side
            if result.returncode == 127:
                print("\033[33mrsync not available on remote — falling back to scp\033[0m")
            else:
                self._print_transfer_summary(result.returncode, elapsed)
                return result.returncode

        # scp fallback
        cmd = self._build_scp_command(ssh_options, local_path, remote_spec, remote_path, direction)
        t0 = time.monotonic()
        result = subprocess.run(cmd)
        elapsed = time.monotonic() - t0
        self._print_transfer_summary(result.returncode, elapsed)
        return result.returncode

    @staticmethod
    def _find_rsync() -> tuple:
        """Find the best local rsync binary and its version.

        macOS ships openrsync at /usr/bin/rsync (reports as 2.6.9) which
        shadows Homebrew's real rsync. This method prefers Homebrew's
        binary when available.

        Returns (path, major, minor) or (None, 0, 0) if not found.
        """
        import re
        # Prefer Homebrew rsync over macOS openrsync
        candidates = [
            '/opt/homebrew/bin/rsync',  # Apple Silicon
            '/usr/local/bin/rsync',     # Intel Mac
        ]
        # Fall back to whatever is on PATH
        path_rsync = shutil.which('rsync')
        if path_rsync:
            candidates.append(path_rsync)

        for path in candidates:
            try:
                out = subprocess.run(
                    [path, '--version'], capture_output=True, text=True, timeout=5,
                ).stdout
                m = re.search(r'version\s+(\d+)\.(\d+)', out)
                if m:
                    major, minor = int(m.group(1)), int(m.group(2))
                    # Skip openrsync (reports 2.6.9, missing modern flags)
                    if 'openrsync' in out:
                        continue
                    return path, major, minor
            except Exception:
                continue

        # No real rsync found; return whatever is on PATH (may be openrsync)
        if path_rsync:
            return path_rsync, 2, 6
        return None, 0, 0

    def _build_rsync_command(self, ssh_cmd_str: str, local_path: str,
                             remote_spec: str, remote_path: str,
                             direction: str) -> List[str]:
        """Build an rsync command list.

        Uses --info=progress2 for a single overall progress line when the
        local rsync supports it (>= 3.1.0). Falls back to quiet -az for
        stock macOS openrsync.
        """
        rsync_path, major, minor = self._find_rsync()
        cmd = [rsync_path or 'rsync', '-az', '--partial']
        if (major, minor) >= (3, 1):
            cmd.append('--info=progress2')
        cmd += ['-e', ssh_cmd_str]
        if direction == 'upload':
            cmd += [local_path, f'{remote_spec}:{remote_path}']
        else:
            cmd += [f'{remote_spec}:{remote_path}', local_path]
        return cmd

    def _build_scp_command(self, ssh_options: List[str], local_path: str,
                           remote_spec: str, remote_path: str,
                           direction: str) -> List[str]:
        """Build an scp command list."""
        cmd = ['scp', '-r', '-o', 'ConnectTimeout=10']
        cmd.extend(ssh_options)
        if direction == 'upload':
            cmd += [local_path, f'{remote_spec}:{remote_path}']
        else:
            cmd += [f'{remote_spec}:{remote_path}', local_path]
        return cmd

    @staticmethod
    def _print_transfer_summary(returncode: int, elapsed: float) -> None:
        """Print a colorized one-line transfer summary."""
        elapsed_str = f"{elapsed:.1f}s"
        if returncode == 0:
            print(f"\033[32m✓ Transfer complete ({elapsed_str})\033[0m")
        else:
            print(f"\033[31m✗ Transfer failed (exit code {returncode})\033[0m")

    def run_job(self, agent: Agent = None, capabilities: list = None, config: str = None,
                hostname: str = None, package: str = None, endpoint_id: str = None) -> dict:
        """
        Run a job on an Aegis agent or on an enrolled endpoint.

        Name the target with a hostname, for an agent's own host asset, or with a package,
        for an Android application already registered by sdk.apks.add(). A package targets
        '#apk#<package>' -- what every mobile capability matches against, and the asset its
        findings are filed on.

        An Aegis v2 endpoint runs the job only when endpoint_id names it. The endpoint is
        not taken from a v2 agent automatically: dispatching to a device is a decision the
        caller makes rather than a consequence of which row they had selected.

        Apart from the legacy agent argument, every parameter is a string or a list, so
        this method is callable over the MCP server as well as from Python. There is no
        second code path for MCP.

        :param agent: Agent object from sdk.aegis.list(), naming a v1 agent's host as the
            target. Prefer hostname; this exists so existing positional callers keep working.
        :type agent: Agent or None
        :param capabilities: Capability names to run. When omitted, no job is created and
            the capabilities available for the named target are returned instead.
        :type capabilities: list or None
        :param config: JSON object string of capability parameters, e.g.
            '{"command": "getprop ro.build.fingerprint"}'
        :type config: str or None
        :param hostname: Hostname of an Aegis agent, to target that agent's host asset
        :type hostname: str or None
        :param package: Android application ID, e.g. 'com.bank.app', to target '#apk#<package>'
        :type package: str or None
        :param endpoint_id: Enrolled Aegis v2 endpoint to run the job on, as shown by
            "guard aegis list --details". Passed to Guard as the job's endpoint_agent_id.
            Guard reserves that key for Praetorian users and silently drops it for everyone
            else, in which case the job falls back to automatic endpoint selection.
        :type endpoint_id: str or None
        :return: When capabilities are given, a dict with 'success', 'job_id', 'job_key',
            'status', 'target_key' and 'endpoint_id'. Otherwise a dict with 'capabilities'.
        :rtype: dict
        :raises Exception: If no target is named, if two are, if a v2 agent is named without
            an endpoint_id, or if the named endpoint is not enrolled, connected and accepting work

        **Example Usage:**
            >>> # What can run against an APK on an enrolled endpoint
            >>> sdk.aegis.run_job(package='com.bank.app')

            >>> # Dispatch a mobile capability to a named device
            >>> sdk.aegis.run_job(capabilities=['android-device-survey'],
            >>>                   package='com.bank.app',
            >>>                   endpoint_id='16169bc5-7943-4783-af81-c4735616f7e9')

            >>> # Dispatch a host capability to an Aegis agent, as before
            >>> sdk.aegis.run_job(capabilities=['linux-enum'], hostname='agent01')
        """
        # A v2 endpoint is reached only through the pin. Without one this is the legacy
        # path, which has no way to route to a device, so it refuses rather than quietly
        # running the job somewhere else.
        if is_v2_agent(agent) and not endpoint_id:
            raise Exception(
                "Aegis v2 endpoint job execution is not supported by the legacy "
                "Aegis job path; refusing to run without endpoint_agent_id"
            )

        if agent is not None and not hostname and not package and not is_v2_agent(agent):
            hostname = agent.hostname or 'unknown'

        if hostname and package:
            raise Exception('A job has one target: pass either hostname or package, not both.')

        if not capabilities:
            return {'capabilities': sorted(self._offerable_capabilities(package, endpoint_id),
                                           key=lambda capability: capability.get('name', ''))}

        target_key = self._target_key(hostname, package)

        # Checked before the job is created, not after. Guard queues a job for an endpoint
        # that cannot run it just as readily as for one that can, and the job then sits at
        # its initial status with nothing saying why -- which reads as a silent success.
        if endpoint_id:
            self._verify_endpoint_can_accept_work(endpoint_id)

        jobs = self.api.jobs.add(target_key, list(capabilities), self._job_config(config, endpoint_id))
        if not jobs:
            raise Exception("No job returned from API")

        job = jobs[0] if isinstance(jobs, list) else jobs
        job_key = job.get('key', '')
        status = job.get('status', 'unknown')

        return {
            'success': True,
            'job_id': job_key.split('#')[-1][:12] if job_key else 'unknown',
            'job_key': job_key,
            'status': status,
            'target_key': target_key,
            'endpoint_id': endpoint_id or '',
        }

    def _offerable_capabilities(self, package: str = None, endpoint_id: str = None) -> List[dict]:
        """Capabilities worth offering for the target the caller has named.

        An APK target gets the capabilities registered against APKs and dispatchable to an
        enrolled endpoint, so a host capability is never offered for an application. With
        no target named, the host capabilities are listed as before.
        """
        if package:
            return self.get_capabilities(target='apk', endpoint_kind=ENDPOINT_KIND_AEGIS, executor='')
        if endpoint_id:
            return self.get_capabilities(endpoint_kind=ENDPOINT_KIND_AEGIS, executor='')
        return self.get_capabilities(surface_filter='internal')

    @staticmethod
    def _target_key(hostname: str = None, package: str = None) -> str:
        if package:
            return f"#apk#{package}"
        if hostname:
            return f"#asset#{hostname}#{hostname}"
        raise Exception('No target for the job. Pass hostname to target an Aegis agent, or '
                        'package to target an APK, e.g. package="com.bank.app".')

    def _endpoint_row(self, endpoint_id: str) -> Optional[dict]:
        """The durable inventory row for one endpoint, or None if it is not enrolled."""
        for row in self._list_endpoint_inventory_rows():
            if _endpoint_row_id(row) == endpoint_id:
                return row
        return None

    def _verify_endpoint_can_accept_work(self, endpoint_id: str) -> dict:
        endpoint = self._endpoint_row(endpoint_id)
        if endpoint is None:
            raise Exception(f'Endpoint "{endpoint_id}" is not enrolled. '
                            f'Run "guard aegis list --details" to see the enrolled endpoints.')

        state = endpoint.get('connectionState') or 'unknown'
        if state != ENDPOINT_STATE_ONLINE:
            raise Exception(f'Endpoint "{endpoint_id}" is {state}, so it cannot pick up this job. '
                            f'Bring the device back online and try again.')

        if endpoint.get('taskDispatchPaused'):
            raise Exception(f'Endpoint "{endpoint_id}" is online but has task dispatch paused, '
                            f'so it would not pick up this job.')

        return endpoint

    @staticmethod
    def _job_config(config: str = None, endpoint_id: str = None) -> Optional[str]:
        """Merge the endpoint pin into the caller's config, without losing what they set."""
        merged = {}
        if isinstance(config, dict):
            merged = dict(config)
        elif config and config.strip():
            try:
                merged = json.loads(config)
            except json.JSONDecodeError as e:
                raise Exception(f'config is not valid JSON: {e}')
            if not isinstance(merged, dict):
                raise Exception('config must be a JSON object, e.g. \'{"command": "id"}\'')

        if endpoint_id:
            merged[ENDPOINT_PIN_CONFIG_KEY] = endpoint_id

        return json.dumps(merged) if merged else None

    def format_agents_list(self, details: bool = False, filter_text: str = None):
        """
        Format agents list for display with optional filtering and details.

        Retrieves all Aegis agents and formats them for CLI display, with optional
        filtering by hostname, client ID, or OS, and optional detailed information
        including system specs and tunnel status.

        :param details: Whether to show detailed agent information
        :type details: bool
        :param filter_text: Filter agents by hostname, client_id, or OS (case-insensitive)
        :type filter_text: str or None
        :return: Formatted agent list information
        :rtype: str

        **Example Usage:**
            >>> # Simple agent list
            >>> result = sdk.aegis.format_agents_list()
            >>> print(result)
            
            >>> # Detailed agent list with filtering
            >>> result = sdk.aegis.format_agents_list(details=True, filter_text="windows")
            >>> print(result)
        """
        warnings = []
        agents_data, _ = self.list(on_warning=warnings.append)
        warning_text = ''.join(f'Warning: {message}\n' for message in warnings)

        if not agents_data:
            return warning_text + (
                'No agents returned from available inventories.'
                if warnings else 'No agents found.'
            )
        
        if filter_text:
            filter_lower = filter_text.lower()
            agents_data = [
                agent for agent in agents_data
                if filter_lower in (agent.hostname or '').lower()
                or filter_lower in (agent.display_id or '').lower()
                or filter_lower in (agent.os or '').lower()
            ]

        if not agents_data:
            return warning_text + f"No agents found matching filter: {filter_text}"
        
        if details:
            detailed_lines = []
            for i, agent in enumerate(agents_data, 1):
                agent_details = agent.to_detailed_string()
                # Add agent number to the first line
                lines = agent_details.split('\n')
                if lines:
                    lines[0] = f"[{i:2d}] {lines[0].lstrip()}"
                detailed_lines.append('\n'.join(lines))
            return warning_text + '\n\n'.join(detailed_lines)
        else:
            lines = [f"{'#':>4}  {'VERSION':<7}  {'HOSTNAME':<30}  ID"]
            for i, agent in enumerate(agents_data, 1):
                lines.append(f"{i:>4}  {agent.version:<7}  {(agent.hostname or 'Unknown')[:30]:<30}  {agent.display_id}")
            return warning_text + '\n'.join(lines)


def _by_name(capabilities: List[dict], name: str) -> Optional[dict]:
    for capability in capabilities:
        if isinstance(capability, dict) and capability.get('name', '').lower() == name.lower():
            return capability
    return None
