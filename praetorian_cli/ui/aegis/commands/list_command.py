"""
List command for displaying agents
"""

from datetime import datetime
from typing import List
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from .base_command import BaseCommand


class ListCommand(BaseCommand):
    """Handle agent listing and loading"""
    
    def execute(self, args: List[str] = None):
        """Execute list command"""
        self.show_agents_list()
    
    def load_agents(self, force_refresh=False):
        """Load agents with 60-second caching and compute status properties"""
        current_time = datetime.now().timestamp()
        
        # Check cache - only fetch if more than 60 seconds have passed
        if current_time - self.menu.last_agent_fetch < self.menu.agent_cache_duration and self.agents and not force_refresh:
            # Use cached agents but still show the list
            self.show_agents_list()
            return
            
        try:
            with self.console.status("[dim]Loading agents...[/dim]"):
                agents_data, _ = self.sdk.aegis.list()
                self.menu.agents = agents_data or []
                       # Update SSH count
                
                self.menu.last_agent_fetch = current_time
                
                # Compute status properties for each agent
                self._compute_agent_properties()
                self.show_agents_list()
                
        except Exception as e:
            self.console.print(f"[red]Error loading agents: {e}[/red]")
            self.menu.agents = []
    
    def _compute_agent_properties(self):
        """Compute and cache status properties for all agents"""
        current_time = datetime.now().timestamp()
        
        for agent in self.agents:
            last_seen = agent.get('last_seen_at', 0)
            
            # Compute agent online/offline status
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            if last_seen > 0 and (current_time - last_seen_seconds) < 60:
                agent['computed_status'] = Text("● ONLINE", style=f"bold {self.colors['success']}")
                agent['computed_last_seen_str'] = datetime.fromtimestamp(last_seen_seconds).strftime("%m/%d %H:%M")
            else:
                agent['computed_status'] = Text("○ OFFLINE", style=f"bold {self.colors['error']}")
                agent['computed_last_seen_str'] = "Never"
            
            # Compute tunnel status and actions
            health = agent.get('health_check', {})
            if health and health.get('cloudflared_status'):
                agent['computed_tunnel_status'] = Text("🔗 ACTIVE", style=f"bold {self.colors['warning']}")
                agent['computed_actions'] = f"[{self.colors['success']}]shell[/{self.colors['success']}], tasks, info"
            else:
                agent['computed_tunnel_status'] = Text("⚬ NONE", style=f"{self.colors['dim']}")
                agent['computed_actions'] = f"[{self.colors['dim']}]shell[/{self.colors['dim']}], tasks, info"
                # Ensure health_check exists
                agent['health_check'] = {'cloudflared_status': False}
       
        self.menu.ssh_count = sum(1 for agent in self.agents 
                            if agent.get('health_check', {}).get('cloudflared_status'))
    
    def show_agents_list(self):
        """Compose and display the agents table using pre-computed properties"""
        if not self.agents:
            no_agents_panel = Panel(
                Align.center(f"[{self.colors['warning']}]No agents currently available[/{self.colors['warning']}]\n\n[dim]Use 'r' to reload or 'q' to quit[/dim]"),
                border_style=self.colors['warning'],
                padding=(2, 4)
            )
            self.console.print(no_agents_panel)
            return
        
        # Professional agents table
        table = Table(
            title=f"[bold {self.colors['primary']}]Aegis Agents[/bold {self.colors['primary']}] [dim]({len(self.agents)} total)[/dim]",
            show_header=True, 
            header_style=f"bold {self.colors['accent']}",
            border_style=self.colors['secondary'],
            title_style=f"bold {self.colors['primary']}",
            show_lines=True
        )
        table.add_column("ID", style=f"{self.colors['accent']}", width=4, justify="center")
        table.add_column("Hostname", style="bold white", min_width=16)
        table.add_column("Operating System", style=f"{self.colors['info']}", width=18)
        table.add_column("Status", width=10, justify="center")
        table.add_column("Tunnel", width=10, justify="center") 
        table.add_column("Last Contact", style=f"{self.colors['dim']}", width=14)
        table.add_column("Available Actions", style=f"{self.colors['secondary']}", min_width=16)
        
        for i, agent in enumerate(self.agents, 1):
            hostname = agent.get('hostname', 'Unknown')
            os_full = agent.get('os', 'unknown').title()
            os_version = agent.get('os_version', '')
            os_display = f"{os_full} {os_version}"[:18]
            
            # Use pre-computed properties from load_agents()/_compute_agent_properties()
            status = agent.get('computed_status', Text("○ OFFLINE", style=f"bold {self.colors['error']}"))
            tunnel_status = agent.get('computed_tunnel_status', Text("⚬ NONE", style=f"{self.colors['dim']}"))
            last_seen_str = agent.get('computed_last_seen_str', "Never")
            actions = agent.get('computed_actions', f"[{self.colors['dim']}]shell[/{self.colors['dim']}], tasks, info")
            
            table.add_row(
                f"[bold]{i:02d}[/bold]",
                hostname,
                os_display,
                status,
                tunnel_status,
                last_seen_str,
                actions
            )
        
        self.console.print(table)
        self.console.print()