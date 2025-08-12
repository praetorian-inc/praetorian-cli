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
        """Show detailed help information with completion features"""
        agent_count = len(self.agents)
        completion_stats = getattr(self.menu, 'completion_manager', None)
        
        help_text = f"""[bold {self.colors['primary']}]CHARIOT AEGIS - Command Reference[/bold {self.colors['primary']}]

[bold {self.colors['success']}]Agent Selection:[/bold {self.colors['success']}]
  [bold {self.colors['success']}]set <id>[/bold {self.colors['success']}]           Set current agent by number (1-{agent_count}), client ID, or hostname
                     [dim]Examples: set 1, set C.abc123, set kali-unit42[/dim]
                     [dim]💡 Use TAB to see all available agents with descriptions[/dim]

[bold {self.colors['success']}]Agent Actions:[/bold {self.colors['success']}] [dim](require selected agent)[/dim]
  [bold {self.colors['success']}]ssh [options][/bold {self.colors['success']}]      Connect to selected agent via SSH (requires tunnel)
                     [dim]Use TAB after 'ssh -' to see all SSH options with help[/dim]
  [bold {self.colors['info']}]info[/bold {self.colors['info']}]              Show detailed system information for selected agent
  [bold {self.colors['warning']}]job <subcommand>[/bold {self.colors['warning']}]  Manage and run jobs on selected agent

[bold {self.colors['accent']}]Job Commands:[/bold {self.colors['accent']}]
  [bold]job list[/bold]          List recent jobs for selected agent
  [bold]job run <cap>[/bold]     Run capability on agent [dim](e.g. process-list)[/dim]
  [bold]job status <id>[/bold]   Check job status
  [bold]job capabilities[/bold]  List available Aegis capabilities

[bold {self.colors['accent']}]SSH Options:[/bold {self.colors['accent']}] [dim](use --help for full details)[/dim]
  [bold {self.colors['warning']}]-D <port>[/bold {self.colors['warning']}]         SOCKS proxy [dim](try: -D 1080)[/dim]
  [bold {self.colors['warning']}]-L <spec>[/bold {self.colors['warning']}]         Local forwarding [dim](try: -L 8080:localhost:80)[/dim]
  [bold {self.colors['warning']}]-R <spec>[/bold {self.colors['warning']}]         Remote forwarding [dim](try: -R 9090:localhost:3000)[/dim]
  [bold {self.colors['warning']}]-i <keyfile>[/bold {self.colors['warning']}]      SSH key file [dim](TAB shows ~/.ssh/ keys)[/dim]
  [bold {self.colors['warning']}]-u <user>[/bold {self.colors['warning']}]         Username [dim](TAB shows common users)[/dim]
  [bold {self.colors['warning']}]-p <port>[/bold {self.colors['warning']}]         Remote port [dim](default: 22)[/dim]

[bold {self.colors['accent']}]System Commands:[/bold {self.colors['accent']}]
  [bold]list[/bold]             Show online agents only (default)
  [bold]list --all[/bold]       Show all agents including offline
  [bold {self.colors['warning']}]reload[/bold {self.colors['warning']}]           Refresh agent list from server
  [bold]clear[/bold]            Clear terminal screen
  [bold]help <cmd>[/bold]       Show help for specific command
  [bold {self.colors['error']}]quit[/bold {self.colors['error']}] / [bold {self.colors['error']}]exit[/bold {self.colors['error']}]     Exit Aegis console

[bold {self.colors['info']}]Completion Features:[/bold {self.colors['info']}]
  • [bold]TAB completion[/bold] with contextual help and descriptions
  • [bold]Intelligent suggestions[/bold] based on current agent list
  • [bold]SSH option help[/bold] with examples and common values
  • [bold]Real-time validation[/bold] and error prevention
  • [bold]Command help[/bold] via --help flag (e.g., ssh --help)
  
[bold {self.colors['warning']}]Examples:[/bold {self.colors['warning']}]
  [dim]# Set agent by various methods[/dim]
  set 1                        [dim]→ Select first agent[/dim]
  set kali-unit42              [dim]→ Select by hostname (TAB completes)[/dim]
  
  [dim]# SSH with port forwarding[/dim]
  ssh -D 1080                  [dim]→ SOCKS proxy on port 1080[/dim]
  ssh -L 8080:localhost:80     [dim]→ Forward local 8080 to remote 80[/dim]
  ssh -u root -i ~/.ssh/mykey  [dim]→ Connect as root with specific key[/dim]
  
  [dim]# Get detailed help[/dim]
  ssh --help                   [dim]→ Full SSH options reference[/dim]
  set --help                   [dim]→ Agent selection guide[/dim]

[bold {self.colors['info']}]💡 Pro Tips:[/bold {self.colors['info']}]
  • Use TAB at any point to see available completions
  • Completion shows descriptions and examples inline
  • Commands validate inputs and show helpful error messages
  • Type partial commands and TAB to see suggestions"""

        if completion_stats:
            stats = completion_stats.get_completion_statistics()
            help_text += f"\n\n[dim]Completion System: {stats['completable_commands']}/{stats['total_commands']} commands enhanced[/dim]"

        self.console.print(Panel(
            help_text,
            border_style=self.colors['accent'],
            padding=(1, 2),
            title="[bold]Help[/bold]",
            title_align="left"
        ))
        self.pause()