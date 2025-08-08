"""
Info command for displaying agent information
"""

import json
from datetime import datetime
from typing import List
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from .base_command import BaseCommand


class InfoCommand(BaseCommand):
    """Handle agent information display"""
    
    def execute(self, args: List[str] = None):
        """Execute info command"""
        self.handle_info_command()
    
    def handle_info_command(self):
        """Handle info command for selected agent"""
        if not self.selected_agent:
            self.console.print("[red]No agent selected! Use 'set <id>' first[/red]")
            self.pause()
            return
        
        self.handle_info(self.selected_agent)
    
    def handle_info(self, agent: dict):
        """Show detailed agent info"""
        self.clear_screen()
        hostname = agent.get('hostname', 'Unknown')
        
        self.console.print(Panel(
            f"[bold]Detailed Info: {hostname}[/bold]",
            style=f"on {self.colors['info']}"
        ))
        
        # Full agent data dump
        self.console.print(Panel(
            json.dumps(agent, default=str, indent=2),
            title="Raw Agent Data",
            border_style="dim"
        ))
        
        self.pause()
    
    def show_agent_details(self, agent: dict):
        """Show professional agent details"""
        hostname = agent.get('hostname', 'Unknown')
        os_info = agent.get('os', 'unknown').title()
        os_version = agent.get('os_version', '')
        architecture = agent.get('architecture', 'Unknown')
        fqdn = agent.get('fqdn', 'N/A')
        client_id = agent.get('client_id', 'N/A')
        last_seen = agent.get('last_seen_at', 0)
        
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
        health = agent.get('health_check', {})
        if health and health.get('cloudflared_status'):
            cf_status = health['cloudflared_status']
            tunnel_name = cf_status.get('tunnel_name', 'N/A')
            public_hostname = cf_status.get('hostname', 'N/A')
            authorized_users = cf_status.get('authorized_users', '').replace(',', ', ')
            
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