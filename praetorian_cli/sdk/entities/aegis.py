from typing import List
import subprocess
import shlex
from praetorian_cli.sdk.model.aegis import Agent


class Aegis:
    """ The methods in this class are to be accessed from sdk.aegis, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self) -> list[Agent]:
        """
        List all Aegis agents.

        Retrieves all Aegis agents from the account, returning them as Agent
        objects with detailed information including system specs, network
        interfaces, and tunnel connectivity status.

        :return: A list of Agent objects
        :rtype: list

        **Example Usage:**
            >>> # List all Aegis agents
            >>> agents, _ = sdk.aegis.list()
            
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
    
    def get_by_client_id(self, client_id: str):
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
                if agent.client_id == client_id:
                    return agent
            return None
        except Exception as e:
            raise Exception(f"Failed to get agent {client_id}: {e}")
    
    def get_capabilities(self, surface_filter: str = None, agent_os: str = None):
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
        try:
            capabilities_response = self.api.capabilities.list(executor='aegis')
            
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
            
            # Apply surface filter
            if surface_filter:
                all_capabilities = [
                    cap for cap in all_capabilities 
                    if isinstance(cap, dict) and cap.get('surface', '').lower() == surface_filter.lower()
                ]
            
            # Apply OS filter
            if agent_os:
                all_capabilities = [
                    cap for cap in all_capabilities
                    if isinstance(cap, dict) and cap.get('name', '').lower().startswith(f'{agent_os.lower()}-')
                ]
            
            return all_capabilities
            
        except Exception as e:
            raise Exception(f"Failed to get Aegis capabilities: {e}")
    
    def validate_capability(self, capability_name: str):
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
            caps = self.get_capabilities()
            for cap in caps:
                if isinstance(cap, dict) and cap.get('name', '').lower() == capability_name.lower():
                    return cap
            return None
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
        config = {
            "aegis": "true",
            "client_id": agent.client_id or '',
            "manual": "true"
        }
        
        if credentials:
            config.update(credentials)
            
        return config
    
    def get_available_ad_domains(self):
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
    
    def ssh_to_agent(self, agent: Agent, user: str = None, 
                     local_forward: List[str] = None, remote_forward: List[str] = None, 
                     dynamic_forward: str = None, key: str = None, ssh_opts: str = None,
                     display_info: bool = True) -> int:
        """
        SSH to an Aegis agent using Cloudflare tunnel
        
        Args:
            agent: The Aegis agent object
            user: SSH username (auto-detected if not provided)
            local_forward: List of local port forwarding specs (e.g., ['8080:localhost:80'])
            remote_forward: List of remote port forwarding specs
            dynamic_forward: Dynamic port forwarding port (e.g., '1080')
            key: SSH private key file path
            ssh_opts: Additional SSH options string
            display_info: Whether to display connection info
            
        Returns:
            SSH process exit code
        """
        from praetorian_cli.handlers.ssh_utils import validate_agent_for_ssh
        
        local_forward = local_forward or []
        remote_forward = remote_forward or []
        
        # Determine SSH username using the centralized method
        if not user:
            _, user = self.api.get_current_user()
        
        # Agent object is already provided as parameter
        
        # Validate agent for SSH
        is_valid, error_msg = validate_agent_for_ssh(agent)
        if not is_valid:
            raise Exception(error_msg)
        
        # Get tunnel information (we know it's valid from validation above)
        hostname = agent.hostname or 'Unknown'
        cf_status = agent.health_check.cloudflared_status
        public_hostname = cf_status.hostname
        authorized_users = cf_status.authorized_users or ''
        tunnel_name = cf_status.tunnel_name or 'N/A'
        
        # Check if user is authorized (if authorization is configured)
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            if user not in users_list:
                import warnings
                warnings.warn(f"User '{user}' may not be authorized for tunnel. Authorized users: {', '.join(users_list)}")
        
        # Build SSH command with performance optimizations
        ssh_command = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30']
        
        # Add SSH key if specified
        if key:
            ssh_command.extend(['-i', key])
        
        # Add local port forwarding (-L)
        for forward in local_forward:
            ssh_command.extend(['-L', forward])
        
        # Add remote port forwarding (-R)
        for forward in remote_forward:
            ssh_command.extend(['-R', forward])
        
        # Add dynamic port forwarding (-D)
        if dynamic_forward:
            ssh_command.extend(['-D', dynamic_forward])
        
        # Add additional SSH options
        if ssh_opts:
            ssh_command.extend(shlex.split(ssh_opts))
        
        # Add the target
        ssh_command.append(f'{user}@{public_hostname}')
        
        # Display connection info if requested
        if display_info:
            print(f"\033[1;36m→ Connecting to {hostname}\033[0m")
            print(f"\033[34m  Gateway: {public_hostname}\033[0m")
            print(f"\033[33m  Tunnel:  {tunnel_name}\033[0m")
            print(f"\033[35m  User:    {user}\033[0m")
            
            # Show port forwarding if configured
            if local_forward:
                print(f"\033[32m  Local:   {', '.join(local_forward)}\033[0m")
            if remote_forward:
                print(f"\033[31m  Remote:  {', '.join(remote_forward)}\033[0m")
            if dynamic_forward:
                print(f"\033[35m  SOCKS:   localhost:{dynamic_forward}\033[0m")
            
            print("")
        
        # Execute SSH command
        try:
            result = subprocess.run(ssh_command)
            return result.returncode
        except KeyboardInterrupt:
            print("\nSSH connection interrupted.")
            return 130
        except FileNotFoundError:
            raise Exception("SSH command not found. Please ensure SSH is installed and in your PATH.")
        except Exception as e:
            raise Exception(f"SSH connection failed: {e}")
    
    def run_job(self, agent: Agent, capabilities: list = None, config: str = None):
        """
        Run a job on an Aegis agent.

        Executes security scanning capabilities against the specified Aegis agent.
        If no capabilities are provided, returns available capabilities for selection.
        Automatically determines the correct target key format based on capability
        requirements (asset vs addomain targets).

        :param agent: The Aegis agent object
        :type agent: Agent
        :param capabilities: List of capability names to execute
        :type capabilities: list or None
        :param config: Optional JSON configuration string for the job
        :type config: str or None
        :return: Job result information or available capabilities if none specified
        :rtype: dict

        **Example Usage:**
            >>> # Get agent first
            >>> agent = sdk.aegis.get_by_client_id("C.6e012b467f9faf82-OG9F0")
            
            >>> # List available capabilities
            >>> result = sdk.aegis.run_job(agent)
            >>> print(result['capabilities'])
            
            >>> # Run specific capability
            >>> result = sdk.aegis.run_job(agent, ["windows-smb-snaffler"])
            >>> print(f"Job queued: {result['job_id']}")
            
            >>> # Run with configuration
            >>> config = '{"Username": "admin", "Password": "secret"}'
            >>> result = sdk.aegis.run_job(agent, ["windows-domain-collection"], config)

        **Return Values:**
            When capabilities are provided:
            - success: Boolean indicating if job was queued successfully
            - job_id: Short job identifier for tracking
            - job_key: Full job key
            - status: Job status
            - message: Success or error message

            When no capabilities provided:
            - capabilities: List of available capability dictionaries
            - message: Informational message
        """
        # Agent object is already provided as parameter
        
        # If no capabilities specified, return available ones
        if not capabilities:
            try:
                caps = self.get_capabilities(surface_filter='internal')
                if caps:
                    return {
                        'capabilities': sorted(caps, key=lambda x: x.get('name', '')),
                        'message': f"Found {len(caps)} available capabilities"
                    }
                else:
                    return {
                        'capabilities': [],
                        'message': "No capabilities found"
                    }
            except Exception as e:
                return {
                    'success': False,
                    'message': f"Error listing capabilities: {e}"
                }
        
        # Create target key - default to asset type
        hostname = agent.hostname or 'unknown'
        target_key = f"#asset#{hostname}#{hostname}"
        
        # Add the job using the existing jobs SDK
        try:
            jobs = self.api.jobs.add(target_key, list(capabilities), config)
            if jobs:
                job = jobs[0] if isinstance(jobs, list) else jobs
                job_key = job.get('key', '')
                status = job.get('status', 'unknown')
                
                return {
                    'success': True,
                    'job_id': job_key.split('#')[-1][:12] if job_key else 'unknown',
                    'job_key': job_key,
                    'status': status,
                    'message': "Job queued successfully"
                }
            else:
                return {
                    'success': False,
                    'message': "No job returned from API"
                }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
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
            return '\n'.join(agent.to_detailed_string() for agent in agents_data)
        else:
            return '\n'.join(str(agent) for agent in agents_data)