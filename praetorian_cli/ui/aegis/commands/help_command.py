"""
Help command using Click's built-in help system
"""

import click
from typing import List
from rich.panel import Panel
from .base_command import BaseCommand
from praetorian_cli.interface_adapters.aegis_commands import AegisContext


class HelpCommand(BaseCommand):
    """Handle help information display using Click's help system"""
    
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
        """Show help for a specific command using Click"""
        try:
            # Create TUI context
            tui_state = type('obj', (), {})()  # Simple object to hold state
            tui_state.selected_agent = self.selected_agent
            aegis_ctx = AegisContext(self.sdk, self.console, tui_state)
            
            # Get the command from shared commands
            cmd = self.sdk.aegis.get_command(None, command_name)    
            if cmd:
                # Create Click context and get help
                ctx = click.Context(cmd)
                ctx.obj = aegis_ctx
                help_text = ctx.get_help()
                
                # Format for Rich display
                self.console.print(Panel(
                    f"[bold]{command_name.upper()}[/bold]\n\n{help_text}",
                    border_style=self.colors['accent'],
                    padding=(1, 2),
                    title=f"[bold]Help: {command_name}[/bold]",
                    title_align="left"
                ))
            else:
                # Handle non-shared commands (system commands)
                self.show_system_command_help(command_name)
                
        except Exception as e:
            self.console.print(f"[red]Error showing help for '{command_name}': {e}[/red]")
        
        self.pause()
    
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
        """Show general help using Click's help plus TUI-specific additions"""
        try:
            # Create TUI context
            tui_state = type('obj', (), {})()  # Simple object to hold state
            tui_state.selected_agent = self.selected_agent
            aegis_ctx = AegisContext(self.sdk, self.console, tui_state)
            
            # Get overall help from Click group
            ctx = click.Context(self.sdk.aegis) 
            ctx.obj = aegis_ctx
            click_help = ctx.get_help()
            
            # Add TUI-specific information
            agent_count = len(self.agents)
            completion_stats = getattr(self.menu, 'completion_manager', None)
            
            tui_additions = f"""

[bold {self.colors['accent']}]TUI-Specific Commands:[/bold {self.colors['accent']}]
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
  job -c windows-smb-snaffler  [dim]→ Run capability on selected agent[/dim]
  list --details               [dim]→ Show detailed agent information[/dim]

[bold {self.colors['info']}]💡 Pro Tips:[/bold {self.colors['info']}]
  • Use 'help <command>' for detailed command help
  • Use '--help' flag on any command (e.g., 'ssh --help')
  • TAB completion shows all available options and examples"""

            if completion_stats:
                stats = completion_stats.get_completion_statistics()
                tui_additions += f"\n\n[dim]Completion System: {stats['completable_commands']}/{stats['total_commands']} commands enhanced[/dim]"

            # Combine Click help with TUI additions
            full_help = f"[bold {self.colors['primary']}]CHARIOT AEGIS - Interactive Console[/bold {self.colors['primary']}]\n\n{click_help}{tui_additions}"
            
            self.console.print(Panel(
                full_help,
                border_style=self.colors['accent'],
                padding=(1, 2),
                title="[bold]Help[/bold]",
                title_align="left"
            ))
            
        except Exception as e:
            self.console.print(f"[red]Error showing help: {e}[/red]")