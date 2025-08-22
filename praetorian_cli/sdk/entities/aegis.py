from typing import List, Optional
import subprocess
from praetorian_cli.sdk.model.aegis import Agent


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


class Aegis:
    """ The methods in this class are to be accessed from sdk.aegis, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api


    def list(self) -> List[Agent]:
        """
        List all Aegis agents.

        Retrieves all Aegis agents from the account, returning them as Agent
        objects with detailed information including system specs, network
        interfaces, and tunnel connectivity status.

        :return: A list of Agent objects
        :rtype: list[Agent]

        **Example Usage:**
            >>> # List all Aegis agents
            >>> agents = sdk.aegis.list()
            
            >>> # Check agent properties
            >>> for agent in agents:
            >>>     print(f"Agent: {agent.hostname}")
            >>>     print(f"OS: {agent.os}")
            >>>     print(f"Has tunnel: {agent.has_tunnel}")
            >>>     print(f"Online: {agent.is_online}")

        **Agent Object Properties:**
            - client_id: Unique identifier for the agent
            - hostname: Agent hostname
            - os: Operating system (e.g., 'linux', 'windows')  
            - network_interfaces: List of NetworkInterface objects
            - has_tunnel: Boolean indicating if Cloudflare tunnel is active
            - is_online: Boolean indicating if agent is currently online
        """
        agents_data = self.api.get('/aegis/agent')
        
        # Return Agent objects
        agents = []
        for agent_data in agents_data:
            agent = Agent.from_dict(agent_data)
            agents.append(agent)
        return agents
    
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
            agents_data = self.list()
            for agent in agents_data:
                if agent.client_id == client_id:
                    return agent
            return None
        except Exception as e:
            raise Exception(f"Failed to get agent {client_id}: {e}")
    
    def get_capabilities(self, surface_filter: str = None, agent_os: str = None) -> List[dict]:
        """
        Get Aegis capabilities with optional filtering.

        Retrieves available capabilities that can be executed by Aegis agents,
        with optional filtering by attack surface and operating system.

        :param surface_filter: Filter by attack surface type (e.g., 'internal', 'external')
        :type surface_filter: str or None
        :param agent_os: Filter by agent operating system (e.g., 'windows', 'linux')
        :type agent_os: str or None
        :return: List of capability dictionaries
        :rtype: list

        **Example Usage:**
            >>> # Get all Aegis capabilities
            >>> caps = sdk.aegis.get_capabilities()
            
            >>> # Get internal surface capabilities only
            >>> internal_caps = sdk.aegis.get_capabilities(surface_filter='internal')
            
            >>> # Get Windows capabilities for internal surface
            >>> win_caps = sdk.aegis.get_capabilities(surface_filter='internal', agent_os='windows')

        **Capability Object Properties:**
            Each capability contains:
            - name: Capability name (e.g., 'windows-smb-snaffler')
            - description: Human-readable description
            - target: Target type ('asset', 'addomain', etc.)
            - surface: Attack surface ('internal', 'external')
            - parameters: List of configurable parameters
        """
        raw = self.api.capabilities.list(executor='aegis')
        caps = normalize_to_list(raw, ["capabilities", "data", "items"]) or []
        caps = [c for c in caps if isinstance(c, dict)]

        if surface_filter:
            sf = surface_filter.lower()
            caps = [c for c in caps if str(c.get("surface", "")).lower() == sf]

        if agent_os:
            os_prefix = f"{agent_os.lower()}-"
            caps = [c for c in caps if str(c.get("name", "")).lower().startswith(os_prefix)]

        return caps
    
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
        caps = self.get_capabilities()
        target = capability_name.lower()
        for cap in caps:
            if str(cap.get("name", "")).lower() == target:
                return cap
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
        domains: List[str] = []
        raw = self.api.assets.list(asset_type='addomain')
        assets = normalize_to_list(raw, ["assets", "data", "items"]) or []

        for asset in assets:
            if not isinstance(asset, dict):
                continue
            dns = asset.get("dns", "")
            key = asset.get("key", "")

            if dns and dns not in domains:
                domains.append(dns)
            elif key and "#addomain#" in key:
                parts = key.split("#")
                if len(parts) >= 3 and parts[1] == "addomain":
                    domain = parts[2]
                    if domain and domain not in domains:
                        domains.append(domain)

        return sorted(domains)
    
    def ssh_to_agent(self, agent: Agent, options: List[str] = None, user: str = None, display_info: bool = True) -> int:
        """SSH to an Aegis agent using Cloudflare tunnel."""
        from praetorian_cli.handlers.ssh_utils import validate_agent_for_ssh

        options = options or []
        # Do not auto-populate user if None; allow '-l' or ssh config to set it
        
        is_valid, error_msg = validate_agent_for_ssh(agent)
        if not is_valid:
            raise Exception(error_msg)
        
        hostname = agent.hostname or 'Unknown'
        cf_status = agent.health_check.cloudflared_status
        public_hostname = cf_status.hostname
        authorized_users = cf_status.authorized_users or ''
        tunnel_name = cf_status.tunnel_name or 'N/A'
        
        if authorized_users and user:
            users_list = [u.strip() for u in authorized_users.split(',')]
            if user not in users_list:
                print(f"User '{user}' may not be authorized for tunnel. Authorized users: {', '.join(users_list)}")
        
        ssh_command = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
        ssh_command.extend(options)
        dest = f'{user}@{public_hostname}' if user else public_hostname
        ssh_command.append(dest)
        
        if display_info:
            print(f"\033[1;36m→ Connecting to {hostname}\033[0m")
            print(f"\033[34m  Gateway: {public_hostname}\033[0m")
            print(f"\033[33m  Tunnel:  {tunnel_name}\033[0m")
            if user:
                print(f"\033[35m  User:    {user}\033[0m")
            
            if local_forward:
                print(f"\033[32m  Local:   {', '.join(local_forward)}\033[0m")
            if remote_forward:
                print(f"\033[31m  Remote:  {', '.join(remote_forward)}\033[0m")
            if dynamic_forward:
                print(f"\033[35m  SOCKS:   localhost:{dynamic_forward}\033[0m")
            print("")

        result = subprocess.run(ssh_command)
        return result.returncode
    
    def run_job(self, agent: Agent, capabilities: list = None, config: str = None):
        """
        Run a job on an Aegis agent.

        If no capabilities are provided, returns available capability dicts under
        the 'capabilities' key. When capabilities are provided, returns a dict
        with keys: 'success', 'job_id', 'job_key', 'status'. Errors raise.
        """
        if not capabilities:
            caps = self.get_capabilities(surface_filter='internal')
            return {
                'capabilities': sorted(caps, key=lambda x: x.get('name', '')),
            }

        hostname = agent.hostname or 'unknown'
        target_key = f"#asset#{hostname}#{hostname}"

        jobs = self.api.jobs.add(target_key, list(capabilities), config)
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
        }
    
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
        agents_data = self.list()
        
        if not agents_data:
            return "No agents found."
        
        if filter_text:
            filter_lower = filter_text.lower()
            agents_data = [agent for agent in agents_data 
                            if filter_lower in agent.hostname.lower() or
                                filter_lower in agent.client_id.lower() or
                                filter_lower in agent.os.lower()]

        if not agents_data:
            return f"No agents found matching filter: {filter_text}"
        
        if details:
            detailed_lines = []
            for i, agent in enumerate(agents_data, 1):
                agent_details = agent.to_detailed_string()
                # Add agent number to the first line
                lines = agent_details.split('\n')
                if lines:
                    lines[0] = f"[{i:2d}] {lines[0].lstrip()}"
                detailed_lines.append('\n'.join(lines))
            return '\n\n'.join(detailed_lines)
        else:
            lines = []
            for i, agent in enumerate(agents_data, 1):
                lines.append(f"[{i:2d}] {str(agent)}")
            return '\n'.join(lines)
