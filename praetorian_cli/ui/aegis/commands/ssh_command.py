"""
SSH command for agent connections
"""

from typing import List
from .base_command import BaseCommand
from praetorian_cli.handlers.ssh_utils import SSHArgumentParser


class SSHCommand(BaseCommand):
    """Handle SSH connections to agents"""
    
    def __init__(self, menu_instance):
        super().__init__(menu_instance)
        self.ssh_parser = SSHArgumentParser(console=self.console)
    
    def execute(self, args: List[str] = None):
        """Execute SSH command"""
        ssh_args = args or []
        self.handle_ssh_command(ssh_args)
    
    def handle_ssh_command(self, ssh_args=None):
        """Handle SSH command for selected agent with optional arguments"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        # Check if SSH is available using shared utility
        if not self.ssh_parser.validate_agent_ssh_availability(self.selected_agent):
            self.console.print()  # Add spacing after error messages
            return
        
        # Parse SSH arguments using shared parser
        ssh_options = self.ssh_parser.parse_ssh_args(ssh_args or [])
        if ssh_options is None:
            return  # Error in parsing, already displayed
        
        # Check if any SSH options were actually provided
        if self.ssh_parser.has_ssh_options(ssh_options):
            # Use the new options-based handler
            self.handle_shell_with_options(self.selected_agent, ssh_options)
        else:
            # Fall back to the original simple SSH handler
            self.handle_shell(self.selected_agent)
    
    
    def handle_shell_with_options(self, agent, options):
        """Execute SSH command with the given options using imported CLI handler"""
        from praetorian_cli.handlers.aegis import _ssh_to_agent
        
        client_id = agent.client_id
        if not client_id:
            self.console.print(f"[red]Agent missing client_id[/red]")
            return
        
        hostname = agent.hostname or 'unknown'
        
        try:
            # Call the SDK SSH method directly
            exit_code = self.sdk.aegis.ssh_to_agent(
                client_id=client_id,
                user=options.get('user'),
                local_forward=options.get('local_forward', []),
                remote_forward=options.get('remote_forward', []), 
                dynamic_forward=options.get('dynamic_forward'),
                key=options.get('key'),
                ssh_opts=' '.join(options.get('passthrough', [])) if options.get('passthrough') else None,
                display_info=True
            )
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[bold green]← SSH session completed[/bold green] [dim]({hostname})[/dim]")
            
        except Exception as e:
            self.console.print(f"[red]Error executing SSH command: {e}[/red]")
    
    def handle_shell(self, agent: dict):
        """Handle simple shell connection without options using imported CLI handler"""
        from praetorian_cli.handlers.aegis import _ssh_to_agent
        
        client_id = agent.client_id
        if not client_id:
            self.console.print(f"[red]Agent missing client_id[/red]")
            self.pause()
            return
        
        hostname = agent.hostname or 'unknown'
        
        try:
            # Call the SDK SSH method directly
            exit_code = self.sdk.aegis.ssh_to_agent(
                client_id=client_id,
                user=None,  # Will auto-detect from SDK
                local_forward=[],
                remote_forward=[],
                dynamic_forward=None,
                key=None,
                ssh_opts=None,
                display_info=True
            )
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[bold green]← SSH session completed[/bold green] [dim]({hostname})[/dim]")
            
        except KeyboardInterrupt:
            self.console.print(f"\n[bold yellow]← Connection interrupted[/bold yellow] [dim]({hostname})[/dim]")
        except FileNotFoundError:
            self.console.print("\n[red]Error: SSH command not found. Please ensure SSH is installed.[/red]")
        except Exception as e:
            self.console.print(f"\n[red]SSH connection failed: {e}[/red]")
        
        self.pause()