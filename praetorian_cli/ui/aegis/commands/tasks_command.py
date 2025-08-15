"""
Tasks command for agent task management
"""

from typing import List
from .base_command import BaseCommand


class TasksCommand(BaseCommand):
    """Handle agent task management"""
    
    def execute(self, args: List[str] = None):
        """Execute tasks command"""
        if not self.selected_agent:
            self.console.print("[red]No agent selected! Use 'set <id>' first[/red]")
            self.pause()
            return
        
        self.handle_tasks(self.selected_agent)
    
    def handle_tasks(self, agent: dict):
        """Handle agent tasks"""
        hostname = agent.hostname or 'unknown'
        self.console.print(f"[blue]Task management for {hostname}[/blue]")
        self.console.print("[dim]Task system implementation pending...[/dim]")
        self.pause()