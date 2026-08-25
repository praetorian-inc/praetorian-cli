"""
Aegis agent data models and structures.

This module contains dataclass definitions for Aegis agent entities,
including network interfaces, tunnel status, health checks, and agent metadata.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class NetworkInterface:
    """Represents a network interface on an agent"""
    name: str
    ip_addresses: List[str]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkInterface':
        return cls(
            name=data.get('name', ''),
            ip_addresses=data.get('ip_addresses', [])
        )


@dataclass 
class CloudflaredStatus:
    """Represents Cloudflared tunnel status"""
    hostname: Optional[str] = None
    tunnel_name: Optional[str] = None
    authorized_users: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CloudflaredStatus':
        return cls(
            hostname=data.get('hostname'),
            tunnel_name=data.get('tunnel_name'),
            authorized_users=data.get('authorized_users')
        )


@dataclass
class HealthCheck:
    """Represents agent health check data"""
    cloudflared_status: Optional[CloudflaredStatus] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthCheck':
        cf_data = data.get('cloudflared_status')
        return cls(
            cloudflared_status=CloudflaredStatus.from_dict(cf_data) if cf_data else None
        )


@dataclass
class Agent:
    """Represents an Aegis agent"""
    client_id: str = 'N/A'
    hostname: str = 'Unknown'
    fqdn: str = 'N/A'
    os: str = 'unknown'
    os_version: str = ''
    architecture: str = 'Unknown'
    last_seen_at: Optional[float] = None
    network_interfaces: List[NetworkInterface] = None
    health_check: Optional[HealthCheck] = None
    key: Optional[str] = None
    endpoint_id: Optional[str] = None
    version: str = 'v1'
    kind: str = 'aegis'
    agent_version: str = ''
    runtime: Optional[Dict[str, Any]] = None
    running_container_count: int = 0
    
    def __post_init__(self):
        if self.network_interfaces is None:
            self.network_interfaces = []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create an Agent from dictionary data"""
        network_interfaces = []
        for iface_data in data.get('network_interfaces', []):
            if isinstance(iface_data, dict):
                network_interfaces.append(NetworkInterface.from_dict(iface_data))
        
        health_data = data.get('health_check')
        health_check = HealthCheck.from_dict(health_data) if health_data else None
        
        return cls(
            client_id=data.get('client_id', 'N/A'),
            hostname=data.get('hostname', 'Unknown'),
            fqdn=data.get('fqdn', 'N/A'),
            os=data.get('os', 'unknown'),
            os_version=data.get('os_version', ''),
            architecture=data.get('architecture', 'Unknown'),
            last_seen_at=data.get('last_seen_at'),
            network_interfaces=network_interfaces,
            health_check=health_check,
            key=data.get('key'),
            version='v1',
            agent_version=data.get('version', '')
        )

    @classmethod
    def from_endpoint_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create an Agent-shaped row from a Guard endpoint registry record."""
        endpoint_id = data.get('endpointId') or data.get('endpoint_id') or ''
        hostname = data.get('hostname') or 'Unknown'
        return cls(
            client_id='N/A',
            hostname=hostname,
            fqdn=hostname,
            os=data.get('os', 'unknown'),
            architecture=data.get('arch') or data.get('architecture') or 'Unknown',
            last_seen_at=parse_timestamp_seconds(
                data.get('lastHeartbeat') or data.get('last_heartbeat')
            ),
            network_interfaces=[],
            health_check=None,
            key=data.get('key'),
            endpoint_id=endpoint_id,
            version='v2',
            kind=data.get('kind', 'aegis'),
            agent_version=data.get('version', ''),
            runtime=data.get('runtime') or {},
            running_container_count=(
                data.get('runningContainerCount') or data.get('running_container_count') or 0
            ),
        )
    
    @property
    def has_tunnel(self) -> bool:
        """Check if agent has an active Cloudflare tunnel"""
        return (self.health_check is not None and 
                self.health_check.cloudflared_status is not None and
                self.health_check.cloudflared_status.hostname is not None)
    
    @property
    def is_online(self) -> bool:
        """Check if agent is currently online."""
        if not self.last_seen_at:
            return False
        
        current_time = datetime.now().timestamp()
        last_seen_seconds = (self.last_seen_at / 1000000 
                           if self.last_seen_at > 1000000000000 
                           else self.last_seen_at)
        online_window_seconds = 90 if self.version == 'v2' else 60
        
        return (current_time - last_seen_seconds) < online_window_seconds

    @property
    def display_id(self) -> str:
        """Return the operator-facing identifier for the endpoint row."""
        return self.endpoint_id or self.client_id or 'N/A'
    
    @property 
    def ip_addresses(self) -> List[str]:
        """Get all non-loopback IP addresses"""
        ips = []
        for iface in self.network_interfaces:
            if iface.name != 'lo':  # Skip loopback
                ips.extend(iface.ip_addresses)
        return [ip for ip in ips if ip]  # Filter empty strings
    
    def __str__(self) -> str:
        """Return a simple string representation of the agent"""
        status = "🔗" if self.has_tunnel else "○"
        return f"{status} [{self.version}] {self.hostname} ({self.display_id})"
    
    def to_detailed_string(self) -> str:
        """Return a detailed string representation of the agent"""
        os_info = f"{self.os} {self.os_version}".strip()
        
        lines = [
            f"\n{self.hostname} ({self.display_id})",
            f"  Version: {self.version}",
            f"  OS: {os_info}",
            f"  Architecture: {self.architecture}",
            f"  FQDN: {self.fqdn}"
        ]
        if self.endpoint_id:
            lines.append(f"  Endpoint ID: {self.endpoint_id}")
        else:
            lines.append(f"  Client ID: {self.client_id}")
        
        if self.has_tunnel:
            cf_status = self.health_check.cloudflared_status
            lines.append(f"  Tunnel: {cf_status.tunnel_name}")
            lines.append(f"  Public hostname: {cf_status.hostname}")
            if cf_status.authorized_users:
                lines.append(f"  Authorized users: {cf_status.authorized_users}")
        else:
            lines.append("  Tunnel: Not configured")
        
        ips = self.ip_addresses
        if ips:
            lines.append(f"  IP addresses: {', '.join(ips)}")
        
        return '\n'.join(lines)


def parse_timestamp_seconds(value: Any) -> Optional[float]:
    """Normalize API timestamp values to epoch seconds."""
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return value / 1000000 if value > 1000000000000 else float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError:
            return None
    return None


def validate_agent_for_ssh(agent: Agent) -> tuple[bool, str]:
    """
    Validate if an agent is ready for SSH connections
    Returns (is_valid, error_message)
    """
    if not agent:
        return False, "No agent specified"
    
    client_id = agent.client_id
    hostname = agent.hostname or 'Unknown'
    has_tunnel = agent.has_tunnel
    
    if not client_id:
        return False, "Agent missing client_id"
    
    # Check if Cloudflare tunnel is available
    if not has_tunnel:
        return False, f"SSH not available for {hostname} - no active tunnel"
    
    # Check if tunnel has a public hostname
    public_hostname = agent.health_check.cloudflared_status.hostname if has_tunnel else None
    if not public_hostname:
        return False, f"No public hostname found in tunnel configuration for {hostname}"
    
    return True, ""
