"""
List command for displaying agents
"""

from datetime import datetime, timedelta
from typing import List
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.box import SIMPLE, MINIMAL, Box
from rich.layout import Layout
from rich.columns import Columns
from .base_command import BaseCommand


class ListCommand(BaseCommand):
    """Handle agent listing and loading"""
    
    def execute(self, args: List[str] = None):
        """Execute list command"""
        args = args or []
        show_offline = '--all' in args or '-a' in args
        self.show_agents_list(show_offline=show_offline)
    
    def load_agents(self, force_refresh=False):
        """Load agents with 60-second caching and compute status properties"""
        current_time = datetime.now().timestamp()
        
        # Check cache - only fetch if more than 60 seconds have passed
        if current_time - self.menu.last_agent_fetch < self.menu.agent_cache_duration and self.agents and not force_refresh:
            # Use cached agents but still show the list
            self.show_agents_list()
            return
            
        try:
            # Use spinner for loading
            with self.console.status(
                f"[{self.colors['dim']}]Loading agents...[/{self.colors['dim']}]",
                spinner="dots",
                spinner_style=f"{self.colors['primary']}"
            ):
                agents_data, _ = self.sdk.aegis.list()
                self.menu.agents = agents_data or []
                
                self.menu.last_agent_fetch = current_time
                
                # Compute status properties for each agent
                self._compute_agent_properties()
                
            # Show the list after loading completes
            self.show_agents_list()
                
        except Exception as e:
            self.console.print(f"  [{self.colors['dim']}]Could not load agents: {e}[/{self.colors['dim']}]")
            self.menu.agents = []
    
    def _compute_agent_properties(self):
        """Compute and cache status properties for all agents"""
        current_time = datetime.now().timestamp()
        
        # Sort: online with tunnel first, then online, then offline
        def agent_sort_key(agent):
            health = agent.get('health_check', {}) or {}
            has_tunnel = bool(health.get('cloudflared_status'))
            last_seen = agent.get('last_seen_at', 0)
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            is_online = last_seen > 0 and (current_time - last_seen_seconds) < 60
            # negative sorting (True first)
            return (
                0 if (is_online and has_tunnel) else (1 if is_online else 2),
                -(last_seen_seconds or 0)
            )

        # Apply in-place stable sort for display order
        self.agents.sort(key=agent_sort_key)

        for agent in self.agents:
            last_seen = agent.get('last_seen_at', 0)
            
            # Compute agent online/offline status
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            if last_seen > 0 and (current_time - last_seen_seconds) < 60:
                agent['computed_last_seen_str'] = self._relative_time(last_seen_seconds, current_time)
                agent['is_online'] = True
            else:
                agent['computed_last_seen_str'] = "—"
                agent['is_online'] = False
            
            # Compute tunnel status
            health = agent.get('health_check', {})
            if health and health.get('cloudflared_status'):
                agent['has_tunnel'] = True
            else:
                agent['has_tunnel'] = False
                # Ensure health_check exists
                agent['health_check'] = {'cloudflared_status': False}
            
            # Add group category for visual separation
            if agent.get('is_online') and agent.get('has_tunnel'):
                agent['group'] = 'active_tunnel'
            elif agent.get('is_online'):
                agent['group'] = 'online'
            else:
                agent['group'] = 'offline'
       
        self.menu.ssh_count = sum(1 for agent in self.agents 
                            if agent.get('health_check', {}).get('cloudflared_status'))
    
    def show_agents_list(self, show_offline=False):
        """Compose and display the agents table using pre-computed properties"""
        if not self.agents:
            no_agents_panel = Panel(
                Align.center(f"[{self.colors['warning']}]No agents available[/{self.colors['warning']}]\n[dim]Press 'r' to reload[/dim]"),
                border_style=self.colors['warning'],
                padding=(1, 2)
            )
            self.console.print(no_agents_panel)
            return
        
        # Count agents by status
        active_tunnel_agents = [a for a in self.agents if a.get('group') == 'active_tunnel']
        online_agents = [a for a in self.agents if a.get('group') == 'online']
        offline_agents = [a for a in self.agents if a.get('group') == 'offline']
        
        # Filter out offline agents unless explicitly requested
        if not show_offline:
            display_agents = active_tunnel_agents + online_agents
        else:
            display_agents = self.agents
        
        # Check if we have any agents to display
        if not display_agents:
            self.console.print()
            if offline_agents:
                self.console.print(f"  No agents online\n")
                self.console.print(f"  [{self.colors['dim']}]• {len(offline_agents)} agents are offline[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Use 'list --all' to see them[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Use 'reload' to refresh[/{self.colors['dim']}]")
            else:
                self.console.print(f"  No agents found\n")
                self.console.print(f"  [{self.colors['dim']}]• Check your network connection[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Verify agents are running[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Use 'reload' to refresh[/{self.colors['dim']}]")
            self.console.print()
            return
        
        # Create minimal status line
        self.console.print()  # Add spacing
        
        # Build minimal status indicators
        status_parts = []
        if active_tunnel_agents:
            status_parts.append(f"{len(active_tunnel_agents)} tunneled")
        if online_agents:
            status_parts.append(f"{len(online_agents)} online")
        if offline_agents and not show_offline:
            status_parts.append(f"[{self.colors['dim']}]{len(offline_agents)} hidden[/{self.colors['dim']}]")
        elif offline_agents:
            status_parts.append(f"[{self.colors['dim']}]{len(offline_agents)} offline[/{self.colors['dim']}]")
        
        if status_parts:
            self.console.print("  " + "   ".join(status_parts))
        
        # Create clean, minimal table
        self.console.print()
        table = Table(
            show_header=True,
            header_style=f"{self.colors['dim']}",
            border_style=self.colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )
        
        table.add_column("", style=f"{self.colors['dim']}", width=4, justify="right", no_wrap=True)
        table.add_column("HOSTNAME", style="white", min_width=25, no_wrap=False)
        table.add_column("OS", style=f"{self.colors['dim']}", width=16, no_wrap=True)
        table.add_column("STATUS", width=8, justify="left", no_wrap=True)
        table.add_column("TUNNEL", width=7, justify="left", no_wrap=True)
        table.add_column("SEEN", style=f"{self.colors['dim']}", width=10, justify="right", no_wrap=True)
        
        # Simplified row display
        for i, agent in enumerate(display_agents, 1):
            hostname = agent.get('hostname', 'Unknown')
            os_full = agent.get('os', 'unknown').lower()
            os_version = agent.get('os_version', '')
            os_display = f"{os_full} {os_version}".strip()[:18]
            
            # Simplified status indicators
            if agent.get('group') == 'active_tunnel':
                status = Text("online", style=f"{self.colors['success']}")
                tunnel = Text("active", style=f"{self.colors['warning']}")
                idx_style = f"{self.colors['warning']}"
                hostname_style = "bold white"
            elif agent.get('group') == 'online':
                status = Text("online", style=f"{self.colors['success']}")
                tunnel = Text("—", style=f"{self.colors['dim']}")
                idx_style = f"{self.colors['success']}"
                hostname_style = "white"
            else:
                status = Text("offline", style=f"{self.colors['dim']}")
                tunnel = Text("—", style=f"{self.colors['dim']}")
                idx_style = f"{self.colors['dim']}"
                hostname_style = f"{self.colors['dim']}"
            
            last_seen = agent.get('computed_last_seen_str', "—")
            if isinstance(last_seen, Text):
                last_seen = last_seen.plain
            
            table.add_row(
                Text(str(i), style=idx_style),
                Text(hostname, style=hostname_style),
                os_display,
                status,
                tunnel,
                last_seen
            )
        
        self.console.print(table)
        self.console.print()

    def _relative_time(self, ts_seconds: float, now_seconds: float) -> str:
        """Render clean, minimal relative time"""
        delta = max(0, int(now_seconds - ts_seconds))
        if delta < 5:
            return "just now"
        if delta < 60:
            return f"{delta}s"
        minutes = delta // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        if hours < 48:
            return "yesterday"
        days = hours // 24
        if days < 7:
            return f"{days}d"
        weeks = days // 7
        if weeks < 4:
            return f"{weeks}w"
        return "long ago"