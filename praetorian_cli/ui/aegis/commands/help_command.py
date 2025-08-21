"""
Help command for TUI interface
"""

from typing import List, Optional
from rich.panel import Panel
from .base_command import BaseCommand
from .help_info import CommandHelpInfo


class HelpCommand(BaseCommand):
    """Handle help information display"""
    
    def execute(self, args: List[str] = None):
        """Execute help command"""
        command_name = args[0] if args else None
        self.show_help(command_name)
    
    def show_help(self, command_name: str = None):
        """Show help information using Click's built-in system"""
        if command_name:
            # Show help for specific command
            self.show_command_help(command_name)
        else:
            # Show overall help
            self.show_general_help()
    
    def show_command_help(self, command_name: str):
        """Show help for a specific command by getting it from the command itself"""
        # Try to get help from command objects first
        command_help = self._get_command_help(command_name)
        
        if command_help:
            # Use the CommandHelpInfo object's built-in formatting method
            help_text = command_help.to_formatted_text(self.colors)
            
            self.console.print(Panel(
                help_text,
                border_style=self.colors['accent'],
                padding=(1, 2),
                title=f"[bold]Help: {command_name}[/bold]",
                title_align="left"
            ))
        else:
            # Handle system commands
            self.show_system_command_help(command_name)
        
        self.pause()
    
    def _get_command_help(self, command_name: str) -> Optional[CommandHelpInfo]:
        """Get help information from the command object itself"""
        # Get the command object from the menu's command registry
        if hasattr(self.menu, 'commands') and command_name in self.menu.commands:
            command_obj = self.menu.commands[command_name]
            return command_obj.get_help_info()
        return None
    
    def show_system_command_help(self, command_name: str):
        """Show help for system commands not handled by shared Click commands"""
        system_helps = {
            'reload': {
                'description': 'Refresh agent list from server',
                'usage': 'reload',
                'examples': ['reload  # Fetch latest agent information']
            },
            'clear': {
                'description': 'Clear terminal screen',
                'usage': 'clear',
                'examples': ['clear  # Clear the console display']
            },
            'quit': {
                'description': 'Exit Aegis console',
                'usage': 'quit',
                'examples': ['quit  # Exit the TUI', 'exit  # Also exits']
            },
            'exit': {
                'description': 'Exit Aegis console',
                'usage': 'exit', 
                'examples': ['exit  # Exit the TUI', 'quit  # Also exits']
            }
        }
        
        if command_name in system_helps:
            help_info = system_helps[command_name]
            help_text = f"""[bold]{help_info['description']}[/bold]

Usage: {help_info['usage']}

Examples:
"""
            for example in help_info['examples']:
                help_text += f"  {example}\n"
                
            self.console.print(Panel(
                help_text.strip(),
                border_style=self.colors['accent'],
                padding=(1, 2),
                title=f"[bold]Help: {command_name}[/bold]",
                title_align="left"
            ))
        else:
            self.console.print(f"[red]Unknown command: {command_name}[/red]")
    
    def show_general_help(self):
        """Show general help for TUI interface by aggregating from all commands"""
        # Get agent count for display
        agent_count = len(self.agents)
        selected_status = "selected" if self.selected_agent else "none selected"
        
        # Build commands section dynamically from all available commands
        commands_section = ""
        if hasattr(self.menu, 'commands'):
            for cmd_name, cmd_obj in self.menu.commands.items():
                if cmd_name != 'help':  # Skip help command itself
                    help_info = cmd_obj.get_help_info()
                    commands_section += f"  [bold]{help_info.name}[/bold]              {help_info.description}\n"
        
        help_text = f"""[bold {self.colors['primary']}]CHARIOT AEGIS - Interactive Console[/bold {self.colors['primary']}]

[bold {self.colors['accent']}]Available Commands:[/bold {self.colors['accent']}]
{commands_section}
[bold {self.colors['accent']}]System Commands:[/bold {self.colors['accent']}]
  [bold]reload[/bold]           Refresh agent list from server
  [bold]clear[/bold]            Clear terminal screen
  [bold]help <cmd>[/bold]       Show help for specific command  
  [bold {self.colors['error']}]quit[/bold {self.colors['error']}] / [bold {self.colors['error']}]exit[/bold {self.colors['error']}]     Exit Aegis console

[bold {self.colors['info']}]TUI Features:[/bold {self.colors['info']}]
  • Commands work without client_id (uses selected agent)
  • TAB completion with contextual help and descriptions
  • Real-time validation and error prevention
  • Rich formatting and interactive prompts

[bold {self.colors['warning']}]Quick Examples:[/bold {self.colors['warning']}]
  set 1                        [dim]→ Select first agent ({agent_count} available)[/dim]
  ssh -D 1080                  [dim]→ SSH with SOCKS proxy[/dim]
  job run windows-smb-snaffler [dim]→ Run capability on selected agent[/dim]
  list --details               [dim]→ Show detailed agent information[/dim]

[bold {self.colors['info']}]Current Status:[/bold {self.colors['info']}]
  • Agents available: {agent_count}
  • Selected agent: {selected_status}

[bold {self.colors['info']}]💡 Pro Tips:[/bold {self.colors['info']}]
  • Use 'help <command>' for detailed command help
  • Use '--help' flag on any command (e.g., 'ssh --help')
  • TAB completion shows all available options and examples"""

        self.console.print(Panel(
            help_text,
            border_style=self.colors['accent'],
            padding=(1, 2),
            title="[bold]Help[/bold]",
            title_align="left"
        ))
        
        self.pause()
    
    def get_help_info(self) -> CommandHelpInfo:
        """Get help information for Help command"""
        return CommandHelpInfo(
            name='help',
            description='Show help information for commands',
            usage='help [command]',
            examples=[
                'help                   # Show general help',
                'help ssh               # Show help for SSH command',
                'help job               # Show help for job command'
            ]
        )