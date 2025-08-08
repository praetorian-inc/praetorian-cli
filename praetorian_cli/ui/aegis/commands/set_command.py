"""
Set command for agent selection
"""

from typing import List
from .base_command import BaseCommand


class SetCommand(BaseCommand):
    """Handle agent selection by number, client ID, or hostname"""
    
    def execute(self, args: List[str] = None):
        """Execute set command"""
        if not args:
            self.console.print("[red]Usage: set <id> - where <id> is agent number, client ID, or hostname[/red]")
            self.pause()
            return
        
        self.handle_select(args[0])
    
    def handle_select(self, identifier: str):
        """Handle agent selection by number, client ID, or hostname"""
        selected_agent = None
        
        # Try by agent number first
        if identifier.isdigit():
            agent_num = int(identifier)
            if 1 <= agent_num <= len(self.agents):
                selected_agent = self.agents[agent_num - 1]
        
        # If not found by number, try by client ID or hostname
        if not selected_agent:
            for agent in self.agents:
                if (agent.get('client_id', '').lower() == identifier.lower() or 
                    agent.get('hostname', '').lower() == identifier.lower()):
                    selected_agent = agent
                    break
        
        if selected_agent:
            self.selected_agent = selected_agent
            hostname = selected_agent.get('hostname', 'Unknown')
            client_id = selected_agent.get('client_id', 'Unknown')
            self.console.print(f"[green]✓ Selected agent: {hostname} ({client_id})[/green]")
        else:
            self.console.print(f"[red]Agent not found: {identifier}[/red]")
            self.console.print(f"[dim]Use agent number (1-{len(self.agents)}), client ID, or hostname[/dim]")
            self.pause()