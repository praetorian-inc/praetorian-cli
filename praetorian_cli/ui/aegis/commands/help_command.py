"""
Help command for displaying command reference
"""

from typing import List
from rich.panel import Panel
from .base_command import BaseCommand


class HelpCommand(BaseCommand):
    """Handle help information display"""
    
    def execute(self, args: List[str] = None):
        """Execute help command"""
        self.show_help()
    
    def show_help(self):
        """Show detailed help information"""
        help_text = f"""[bold {self.colors['primary']}]CHARIOT AEGIS - Command Reference[/bold {self.colors['primary']}]

[bold {self.colors['success']}]Agent Selection:[/bold {self.colors['success']}]
  [bold]set <id>[/bold]        Set current agent by number (1-{len(self.agents)}), client ID, or hostname
                    Examples: set 1, set C.abc123, set kali-unit42

[bold {self.colors['success']}]Agent Actions:[/bold {self.colors['success']}] [dim](require selected agent)[/dim]
  [bold]ssh [options][/bold]   Connect to selected agent via SSH (requires tunnel)
  [bold]info[/bold]           Show detailed system information for selected agent

[bold {self.colors['accent']}]SSH Options:[/bold {self.colors['accent']}]
  [bold]-D <port>[/bold]      Dynamic port forwarding (SOCKS proxy)
  [bold]-L <spec>[/bold]      Local port forwarding (local_port:remote_host:remote_port)
  [bold]-R <spec>[/bold]      Remote port forwarding (remote_port:local_host:local_port)
  [bold]-u <user>[/bold]      Connect as specific user
  [bold]-i <keyfile>[/bold]   Use specific SSH key file

[bold {self.colors['accent']}]System Commands:[/bold {self.colors['accent']}]
  [bold]list[/bold]           Show all agents (refresh main view)
  [bold]reload[/bold]         Refresh agent list from server
  [bold]clear[/bold]          Clear screen
  [bold]help[/bold]           Show this help message
  [bold]quit[/bold] / [bold]exit[/bold]  Exit Aegis console

[bold {self.colors['info']}]Tab Completion:[/bold {self.colors['info']}]
  Press TAB to auto-complete commands and agent identifiers
  
[bold {self.colors['warning']}]Examples:[/bold {self.colors['warning']}]
  set 1 → ssh -D 1080         Set agent and create SOCKS proxy on port 1080
  ssh -L 8080:localhost:80    Forward local port 8080 to remote port 80
  ssh -R 9000:localhost:3000  Forward remote port 9000 to local port 3000
  ssh -u root                 Connect as root user
  set kali-unit42 → info      Set by hostname and show details"""

        self.console.print(Panel(
            help_text,
            border_style=self.colors['accent'],
            padding=(1, 2),
            title="[bold]Help[/bold]",
            title_align="left"
        ))
        self.pause()