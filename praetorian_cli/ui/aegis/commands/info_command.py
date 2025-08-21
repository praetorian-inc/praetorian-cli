"""
Info command for displaying agent information
"""

import json
from datetime import datetime
from typing import List
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.box import MINIMAL
from rich.columns import Columns
from .base_command import BaseCommand
from .help_info import CommandHelpInfo


class InfoCommand(BaseCommand):
    """Handle agent information display"""
    
    def execute(self, args: List[str] = None):
        """Execute info command"""
        args = args or []
        raw = ('--raw' in args) or ('-r' in args)
        self.handle_info_command(raw=raw)
    
    def handle_info_command(self, raw: bool = False):
        """Handle info command for selected agent"""
        agent = self.require_selected_agent()
        if not agent:
            self.pause()
            return
        
        self.handle_info(agent, raw=raw)
    
    def handle_info(self, agent: dict, raw: bool = False):
        """Show detailed agent info with minimal design"""
        self.clear_screen()
        hostname = agent.hostname or 'Unknown'
        
        # Simple header
        self.console.print()
        self.console.print(f"  [{self.colors['primary']}]Agent Details[/{self.colors['primary']}]")
        self.console.print()

        if raw:
            # Raw JSON dump with minimal styling
            self.console.print(f"  [{self.colors['dim']}]Raw agent data:[/{self.colors['dim']}]")
            self.console.print()
            # Format JSON with indentation
            json_lines = json.dumps(agent, default=str, indent=2).split('\n')
            for line in json_lines:
                self.console.print(f"  {line}")
            self.pause()
            return
        
        # Gather agent info
        os_info = (agent.os or 'unknown').lower()
        os_version = agent.os_version or ''
        architecture = agent.architecture or 'Unknown'
        fqdn = agent.fqdn or 'N/A'
        client_id = agent.client_id or 'N/A'
        last_seen = agent.last_seen_at or 0
        health = agent.health_check
        cf_status = health.cloudflared_status if health else None
        
        # Get network interfaces and extract IP addresses
        network_interfaces = agent.network_interfaces or []
        ip_info = []
        
        # Extract IPs from network interfaces
        if network_interfaces:
            for interface in network_interfaces:
                if hasattr(interface, 'name'):  # NetworkInterface object
                    # Get interface name
                    iface_name = interface.name or ''
                    
                    # Get IP addresses from the ip_addresses field (it's a list)
                    ip_addresses = interface.ip_addresses or []
                    
                    # Add each IP with interface name
                    for ip in ip_addresses:
                        if ip:  # Skip empty strings
                            if iface_name and iface_name != 'lo':  # Skip loopback
                                ip_info.append(f"{ip} ({iface_name})")
                            elif iface_name != 'lo':
                                ip_info.append(ip)
        
        # Compute status
        current_time = datetime.now().timestamp()
        if last_seen > 0:
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            is_online = (current_time - last_seen_seconds) < 60
            last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%Y-%m-%d %H:%M:%S")
            if is_online:
                status_text = f"[{self.colors['success']}]● online[/{self.colors['success']}]"
            else:
                status_text = f"[{self.colors['error']}]○ offline[/{self.colors['error']}]"
        else:
            last_seen_str = "never"
            status_text = f"[{self.colors['error']}]○ offline[/{self.colors['error']}]"
            is_online = False

        # Simple, clean output
        self.console.print(f"  [bold white]{hostname}[/bold white]  {status_text}")
        self.console.print(f"  [{self.colors['dim']}]{fqdn}[/{self.colors['dim']}]")
        self.console.print()
        
        # System info
        self.console.print(f"  [{self.colors['dim']}]System[/{self.colors['dim']}]")
        self.console.print(f"    OS:           {os_info} {os_version}")
        self.console.print(f"    Architecture: {architecture}")
        if ip_info:
            if len(ip_info) == 1:
                self.console.print(f"    IP:           {ip_info[0]}")
            else:
                self.console.print(f"    IPs:          {ip_info[0]}")
                for ip in ip_info[1:]:
                    self.console.print(f"                  {ip}")
        self.console.print(f"    Client ID:    {client_id[:40]}...")
        self.console.print(f"    Last seen:    {last_seen_str}")
        self.console.print()
        
        # Tunnel info
        if cf_status:
            tunnel_name = cf_status.tunnel_name or 'N/A'
            public_hostname = cf_status.hostname or 'N/A'
            authorized_users = cf_status.authorized_users or ''
            
            self.console.print(f"  [{self.colors['warning']}]Tunnel active[/{self.colors['warning']}]")
            self.console.print(f"    Name:      {tunnel_name}")
            self.console.print(f"    Public:    {public_hostname}")
            
            if authorized_users:
                users_list = [u.strip() for u in authorized_users.split(',')]
                self.console.print(f"    Authorized: {', '.join(users_list)}")
        else:
            self.console.print(f"  [{self.colors['dim']}]No tunnel configured[/{self.colors['dim']}]")
        
        self.pause()
    
    def show_agent_details(self, agent: dict):
        """Show professional agent details"""
        hostname = agent.hostname or 'Unknown'
        os_info = (agent.os or 'unknown').title()
        os_version = agent.os_version or ''
        architecture = agent.architecture or 'Unknown'
        fqdn = agent.fqdn or 'N/A'
        client_id = agent.client_id or 'N/A'
        last_seen = agent.last_seen_at or 0
        
        # Status
        if last_seen > 0:
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%Y-%m-%d %H:%M:%S UTC")
            status = f"[{self.colors['success']}]● ONLINE[/{self.colors['success']}]"
        else:
            last_seen_str = "Never"
            status = f"[{self.colors['error']}]○ OFFLINE[/{self.colors['error']}]"
        
        # System info table
        system_table = Table(
            title=f"[bold {self.colors['secondary']}]System Information[/bold {self.colors['secondary']}]",
            show_header=False, 
            box=None, 
            padding=(0, 3),
            border_style=self.colors['accent'],
            title_style=f"bold {self.colors['secondary']}"
        )
        system_table.add_column("Property", style=f"{self.colors['accent']}", width=16)
        system_table.add_column("Value", style="white")
        
        system_table.add_row("Status", status)
        system_table.add_row("Operating System", f"{os_info} {os_version}")
        system_table.add_row("Architecture", architecture)
        system_table.add_row("FQDN", fqdn)
        system_table.add_row("Client ID", client_id)
        system_table.add_row("Last Contact", last_seen_str)
        
        # Tunnel info
        health = agent.health_check
        if health and health.cloudflared_status:
            cf_status = health.cloudflared_status
            tunnel_name = cf_status.tunnel_name or 'N/A'
            public_hostname = cf_status.hostname or 'N/A'
            authorized_users = (cf_status.authorized_users or '').replace(',', ', ')
            
            system_table.add_row("", "")  # Spacer
            system_table.add_row("Tunnel Status", f"[{self.colors['warning']}]🔗 ACTIVE[/{self.colors['warning']}]")
            system_table.add_row("Tunnel Name", tunnel_name)
            system_table.add_row("Public Hostname", public_hostname)
            system_table.add_row("Authorized Users", authorized_users)
        else:
            system_table.add_row("", "")  # Spacer  
            system_table.add_row("Tunnel Status", f"[{self.colors['dim']}]⚬ Not configured[/{self.colors['dim']}]")
        
        system_panel = Panel(
            system_table,
            border_style=self.colors['accent'],
            padding=(1, 2)
        )
        self.console.print(system_panel)
    
    def get_help_info(self) -> CommandHelpInfo:
        """Get help information for Info command"""
        return CommandHelpInfo(
            name='info',
            description='Show detailed information for selected agent',
            usage='info [options]',
            options=[
                '--raw, -r             Show raw JSON output'
            ],
            examples=[
                'info                   # Show formatted agent info',
                'info --raw             # Show raw JSON data'
            ]
        )