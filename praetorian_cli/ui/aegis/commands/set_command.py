"""
Set command for agent selection
"""

from typing import List
from .base_command import BaseCommand
from .help_info import CommandHelpInfo


class SetCommand(BaseCommand):
    """Handle agent selection by number, client ID, or hostname"""
    
    def execute(self, args: List[str] = None):
        """Execute set command"""
        if not args:
            self.console.print("[red]Usage: set <id>[/red] [dim](number, client ID, or hostname)[/dim]")
            # Do not block on usage; allow immediate re-prompt
            return
        
        self.handle_select(args[0])
    
    def handle_select(self, identifier: str):
        """Handle agent selection by number, client ID, or hostname - calls SDK directly"""
        selected_agent = None
        
        # Get fresh agent list from SDK
        agents_data = self.sdk.aegis.list()
        
        # Try by agent number first
        if identifier.isdigit():
            agent_num = int(identifier)
            if 1 <= agent_num <= len(agents_data):
                selected_agent = agents_data[agent_num - 1]
        
        # If not found by number, try by client ID or hostname
        if not selected_agent:
            for agent in agents_data:
                if ((agent.client_id or '').lower() == identifier.lower() or 
                    (agent.hostname or '').lower() == identifier.lower()):
                    selected_agent = agent
                    break
        
        if selected_agent:
            # Update TUI context directly
            self.selected_agent = selected_agent
            hostname = selected_agent.hostname or 'Unknown'
            client_id = selected_agent.client_id or 'N/A'
            self.console.print(f"[green]Selected agent: {hostname} ({client_id})[/green]")
        else:
            self.console.print(f"\n  Agent not found: {identifier}")
            self.console.print(f"  [{self.colors['dim']}]Use agent number (1-{len(agents_data)}), client ID, or hostname[/{self.colors['dim']}]\n")
            # No pause; return to prompt
    
    def get_help_info(self) -> CommandHelpInfo:
        """Get help information for Set command"""
        return CommandHelpInfo(
            name='set',
            description='Select an agent for operations',
            usage='set <agent_id_or_number>',
            examples=[
                'set 1                  # Select first agent by number',
                'set C.6e012b467f9faf82  # Select by client ID'
            ]
        )