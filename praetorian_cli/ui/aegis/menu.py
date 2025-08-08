#!/usr/bin/env python3
"""
Aegis Menu Interface - Ultra-fast, clean operator interface
Command-driven approach with tab completion and intuitive UX
"""

import os
import sys
import readline
import shlex
from datetime import datetime
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.layout import Layout
from rich.align import Align


class AegisMenu:
    """Ultra-fast Aegis menu interface with modern command-driven UX"""
    
    def __init__(self, sdk):
        self.sdk = sdk
        self.console = Console()
        self.agents = []
        self.selected_agent = None  # Currently selected agent
        
        # Get user information using the centralized, reliable method
        self.user_email, self.username = self.sdk.get_current_user()
        
        # Professional Praetorian color scheme
        self.colors = {
            'primary': '#5F47B7',      # Primary purple
            'secondary': '#8F7ECD',    # Secondary purple  
            'accent': '#BFB5E2',       # Tertiary purple
            'dark': '#0D0D28',         # Dark primary
            'dark_sec': '#191933',     # Dark secondary
            'success': '#4CAF50',      # Green
            'error': '#F44336',        # Red
            'warning': '#FFC107',      # Yellow
            'info': '#2196F3',         # Blue
            'text': '#FFFFFF',         # White text
            'dim': '#B6B6BE'           # Light secondary
        }
        
        # Available commands for tab completion
        self.commands = [
            'set', 'ssh', 'info', 'list', 'reload', 'clear', 'help', 'quit', 'exit'
        ]
        
        # Setup tab completion
        self.setup_tab_completion()
    
    def setup_tab_completion(self):
        """Setup readline tab completion for commands and agent identifiers"""
        def completer(text, state):
            options = []
            
            # Get the current line to understand context
            line = readline.get_line_buffer()
            words = line.split()
            
            if not words or (len(words) == 1 and not line.endswith(' ')):
                # Completing the first word (command)
                options = [cmd for cmd in self.commands if cmd.startswith(text)]
            elif len(words) >= 1:
                command = words[0].lower()
                if command == 'set' and len(words) <= 2:
                    # Completing agent ID or number for set command
                    options = []
                    for i, agent in enumerate(self.agents):
                        agent_num = str(i + 1)
                        client_id = agent.get('client_id', '')
                        hostname = agent.get('hostname', '')
                        
                        # Add numeric options
                        if agent_num.startswith(text):
                            options.append(agent_num)
                        # Add client ID options
                        if client_id.startswith(text):
                            options.append(client_id)
                        # Add hostname options
                        if hostname.startswith(text):
                            options.append(hostname)
                            
                elif command == 'ssh':
                    # SSH command completion
                    ssh_options = ['-D', '-L', '-R', '-u', '-i']
                    if text.startswith('-'):
                        # Completing SSH options
                        options = [opt for opt in ssh_options if opt.startswith(text)]
                    elif len(words) >= 2 and words[-2] in ['-D']:
                        # Common SOCKS proxy ports
                        common_ports = ['1080', '8080', '9050']
                        options = [port for port in common_ports if port.startswith(text)]
                    elif len(words) >= 2 and words[-2] in ['-u']:
                        # Common usernames
                        common_users = ['root', 'admin', 'user', self.username or '']
                        options = [user for user in common_users if user and user.startswith(text)]
            
            try:
                return options[state]
            except IndexError:
                return None
        
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        # Enable case-insensitive completion
        readline.parse_and_bind("set completion-ignore-case on")
    
    def run(self):
        """Main interface loop"""
        self.clear_screen()
        self.load_agents()
        
        while True:
            try:
                self.show_main_menu()
                choice = self.get_input()
                
                if not self.handle_choice(choice):
                    break
                    
            except KeyboardInterrupt:
                self.console.print("\n[dim]Goodbye![/dim]")
                break
    
    def clear_screen(self):
        """Clear the screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def load_agents(self):
        """Load agents quickly"""
        try:
            with self.console.status("[dim]Loading agents...[/dim]"):
                agents_data, _ = self.sdk.aegis.list()
                self.agents = agents_data or []
                
        except Exception as e:
            self.console.print(f"[red]Error loading agents: {e}[/red]")
            self.agents = []
    
    def show_main_menu(self):
        """Show the main interface"""
        self.clear_screen()
        
        # Professional header without ASCII art
        current_account = self.sdk.keychain.account
        if current_account and current_account != self.user_email:
            # Show both user and account if they're different (assumed role)
            user_info = f"User: {self.user_email} • Account: {current_account} • SSH as: {self.username}"
        else:
            # Show just user and SSH username if no assumed role
            user_info = f"User: {self.user_email} • SSH as: {self.username}"
            
        header_content = f"""[bold white]CHARIOT AEGIS[/bold white] [dim white]│[/dim white] [bold {self.colors['accent']}]Interactive Console[/bold {self.colors['accent']}]
[dim {self.colors['dim']}]Unified Agent Management • Direct SSH Access • Real-time Operations[/dim {self.colors['dim']}]
[dim {self.colors['dim']}]{{user_info}}[/dim {self.colors['dim']}]""".format(user_info=user_info)
        
        self.console.print(Panel(
            Align.center(header_content),
            style=f"bold white on {self.colors['dark_sec']}",
            border_style=self.colors['primary'],
            padding=(1, 2),
            title="[bold]CHARIOT[/bold]",
            title_align="left"
        ))
        
        self.console.print()
        
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
            title=f"[bold {self.colors['primary']}]Active Agents[/bold {self.colors['primary']}] [dim]({len(self.agents)} total)[/dim]",
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
            last_seen = agent.get('last_seen_at', 0)
            
            # Professional status indicators
            if last_seen > 0:
                status = Text("● ONLINE", style=f"bold {self.colors['success']}")
                last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
                last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%m/%d %H:%M")
            else:
                status = Text("○ OFFLINE", style=f"bold {self.colors['error']}")
                last_seen_str = "Never"
            
            # Tunnel status with professional indicators
            health = agent.get('health_check', {})
            if health and health.get('cloudflared_status'):
                tunnel_status = Text("🔗 ACTIVE", style=f"bold {self.colors['warning']}")
                actions = f"[{self.colors['success']}]shell[/{self.colors['success']}], tasks, info"
            else:
                tunnel_status = Text("⚬ NONE", style=f"{self.colors['dim']}")
                actions = f"[{self.colors['dim']}]shell[/{self.colors['dim']}], tasks, info"
                agent['health_check'] = {'cloudflared_status': False}
            
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
        
        # Count SSH-capable agents
        ssh_count = sum(1 for agent in self.agents 
                       if agent.get('health_check', {}).get('cloudflared_status'))
        
        # Selected agent info
        selected_info = ""
        if self.selected_agent:
            hostname = self.selected_agent.get('hostname', 'Unknown')
            client_id = self.selected_agent.get('client_id', 'Unknown')
            selected_info = f"[bold {self.colors['success']}]Selected Agent:[/bold {self.colors['success']}] {hostname} ({client_id})"
        else:
            selected_info = f"[{self.colors['dim']}]No agent selected - use 'set <id>' to choose an agent[/{self.colors['dim']}]"

        # Modern command reference with clear syntax
        cmd_panel = Panel(
            f"""[bold {self.colors['primary']}]Available Commands[/bold {self.colors['primary']}] [dim]({ssh_count}/{len(self.agents)} agents have SSH capability)[/dim]
{selected_info}

[bold {self.colors['success']}]🔗 Agent Selection & Actions:[/bold {self.colors['success']}]
  [bold {self.colors['success']}]set <id>[/bold {self.colors['success']}] → Set current agent by number, client ID, or hostname
  [bold {self.colors['success']}]ssh [options][/bold {self.colors['success']}] → Connect to selected agent via SSH
  [bold {self.colors['info']}]info[/bold {self.colors['info']}] → Show detailed information for selected agent
  
[bold {self.colors['accent']}]System Commands:[/bold {self.colors['accent']}]
  [bold]list[/bold] → Show all agents    [bold {self.colors['warning']}]reload[/bold {self.colors['warning']}] → Refresh agent list
  [bold]clear[/bold] → Clear screen    [bold]help[/bold] → Show this help    [bold {self.colors['error']}]quit[/bold {self.colors['error']}] → Exit

[dim]💡 Tips: Use TAB for auto-completion • Type 'set 1' or 'ssh -D 1080' for SOCKS proxy[/dim]""",
            border_style=self.colors['accent'],
            padding=(1, 2),
            title="[dim]Commands[/dim]",
            title_align="left"
        )
        self.console.print(cmd_panel)
    
    def get_input(self) -> str:
        """Get user input with tab completion support"""
        try:
            # Build prompt with selected agent info
            if self.selected_agent:
                hostname = self.selected_agent.get('hostname', 'Unknown')
                prompt = f"aegis({hostname})> "
            else:
                prompt = "aegis> "
            
            # Set readline prompt for proper display
            readline.set_startup_hook(lambda: readline.insert_text(""))
            
            # Get input with tab completion
            user_input = input(prompt).strip()
            return user_input
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C and Ctrl+D gracefully
            return "quit"
    
    def handle_choice(self, choice: str) -> bool:
        """Handle user choice with modern command parsing"""
        if not choice:
            return True  # Just refresh
        
        # Parse the command using shlex for proper argument splitting
        try:
            args = shlex.split(choice)
        except ValueError:
            self.console.print(f"[red]Invalid command syntax: {choice}[/red]")
            self.pause()
            return True
        
        if not args:
            return True
        
        command = args[0].lower()  # Only convert command name to lowercase, preserve argument case
        
        # Handle commands
        if command in ['q', 'quit', 'exit']:
            return False
            
        elif command in ['r', 'reload']:
            self.load_agents()
            self.console.print("[green]Agent list reloaded![/green]")
            
        elif command == 'clear':
            self.clear_screen()
            
        elif command in ['h', 'help']:
            self.show_help()
            
        elif command == 'list':
            # Just refresh the main view to show agents
            pass
            
        elif command == 'set':
            if len(args) < 2:
                self.console.print("[red]Usage: set <id> - where <id> is agent number, client ID, or hostname[/red]")
                self.pause()
            else:
                self.handle_select(args[1])
                
        elif command == 'ssh':
            ssh_args = args[1:] if len(args) > 1 else []
            self.handle_ssh_command(ssh_args)
            
        elif command == 'info':
            self.handle_info_command()
            
        # Legacy support for direct numbers (backwards compatibility)
        elif command.isdigit():
            agent_num = int(command)
            if 1 <= agent_num <= len(self.agents):
                self.selected_agent = self.agents[agent_num - 1]
                hostname = self.selected_agent.get('hostname', 'Unknown')
                self.console.print(f"[green]Selected agent: {hostname}[/green]")
            else:
                self.console.print(f"[red]Invalid agent number: {agent_num}[/red]")
                self.pause()
                
        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
            self.console.print("[dim]Type 'help' for available commands[/dim]")
            self.pause()
        
        return True
    
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
    
    def handle_ssh_command(self, ssh_args=None):
        """Handle SSH command for selected agent with optional arguments"""
        if not self.selected_agent:
            self.console.print("[red]No agent selected! Use 'set <id>' first[/red]")
            self.pause()
            return
        
        # Check if SSH is available
        health = self.selected_agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            hostname = self.selected_agent.get('hostname', 'Unknown')
            self.console.print(f"[red]SSH not available for {hostname}[/red]")
            self.console.print("[dim]This agent doesn't have an active Cloudflare tunnel.[/dim]")
            self.pause()
            return
        
        # Parse SSH arguments
        ssh_options = self.parse_ssh_args(ssh_args or [])
        if ssh_options is None:
            return  # Error in parsing, already displayed
        
        # Check if any SSH options were actually provided
        has_options = (
            ssh_options['local_forward'] or 
            ssh_options['remote_forward'] or 
            ssh_options['dynamic_forward'] or
            ssh_options['key'] or
            ssh_options['user']
        )
        
        if has_options:
            # Use the new options-based handler
            self.handle_shell_with_options(self.selected_agent, ssh_options)
        else:
            # Fall back to the original simple SSH handler
            self.handle_shell(self.selected_agent)
    
    def parse_ssh_args(self, args):
        """Parse SSH command arguments and return options dict"""
        options = {
            'local_forward': [],
            'remote_forward': [],
            'dynamic_forward': None,
            'key': None,
            'ssh_opts': None,
            'user': None
        }
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg in ['-L', '-l', '--local-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -L requires a port forwarding specification[/red]")
                    self.console.print("[dim]Example: ssh -L 8080:localhost:80[/dim]")
                    self.pause()
                    return None
                options['local_forward'].append(args[i + 1])
                i += 2
                
            elif arg in ['-R', '-r', '--remote-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -R requires a port forwarding specification[/red]")
                    self.console.print("[dim]Example: ssh -R 9090:localhost:3000[/dim]")
                    self.pause()
                    return None
                options['remote_forward'].append(args[i + 1])
                i += 2
                
            elif arg in ['-D', '-d', '--dynamic-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -D requires a port number[/red]")
                    self.console.print("[dim]Example: ssh -D 1080[/dim]")
                    self.pause()
                    return None
                try:
                    port = int(args[i + 1])
                    if port < 1 or port > 65535:
                        raise ValueError()
                    options['dynamic_forward'] = str(port)
                except ValueError:
                    self.console.print(f"[red]Error: Invalid port number '{args[i + 1]}'[/red]")
                    self.console.print("[dim]Port must be a number between 1 and 65535[/dim]")
                    self.pause()
                    return None
                i += 2
                
            elif arg in ['-i', '-I', '--key']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -i requires a key file path[/red]")
                    self.console.print("[dim]Example: ssh -i ~/.ssh/my_key[/dim]")
                    self.pause()
                    return None
                options['key'] = args[i + 1]
                i += 2
                
            elif arg in ['-u', '-U', '--user']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -u requires a username[/red]")
                    self.console.print("[dim]Example: ssh -u root[/dim]")
                    self.pause()
                    return None
                options['user'] = args[i + 1]
                i += 2
                
            elif arg.startswith('-'):
                self.console.print(f"[red]Error: Unknown SSH option '{arg}'[/red]")
                self.console.print("[dim]Supported options: -L, -R, -D, -i, -u[/dim]")
                self.console.print("[dim]Type 'help' for examples[/dim]")
                self.pause()
                return None
            else:
                self.console.print(f"[red]Error: Unexpected argument '{arg}'[/red]")
                self.pause()
                return None
            
        return options
    
    def handle_shell_with_options(self, agent, options):
        """Execute SSH command with the given options directly"""
        import subprocess
        import sys
        import time
        
        hostname = agent.get('hostname', 'unknown')
        
        # Check tunnel (same as original handle_shell)
        health = agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            self.console.print(f"[red]No Cloudflare tunnel available for {hostname}[/red]")
            self.pause()
            return
        
        # Get tunnel information
        cf_status = health['cloudflared_status']
        public_hostname = cf_status.get('hostname')
        authorized_users = cf_status.get('authorized_users', '')
        tunnel_name = cf_status.get('tunnel_name', 'N/A')
        
        if not public_hostname:
            self.console.print(f"[red]No public hostname found in tunnel configuration for {hostname}[/red]")
            self.pause()
            return
        
        # Determine SSH user
        ssh_user = options.get('user') or self.username
        
        # Show connection info
        self.console.print(f"[green]Connecting to {hostname} via {public_hostname}...[/green]")
        self.console.print(f"[dim]Tunnel: {tunnel_name}[/dim]")
        self.console.print(f"[dim]SSH user: {ssh_user}[/dim]")
        
        # Show port forwarding info
        if options['local_forward']:
            self.console.print(f"[dim]Local forwarding: {', '.join(options['local_forward'])}[/dim]")
        if options['remote_forward']:
            self.console.print(f"[dim]Remote forwarding: {', '.join(options['remote_forward'])}[/dim]")
        if options['dynamic_forward']:
            self.console.print(f"[dim]SOCKS proxy: localhost:{options['dynamic_forward']}[/dim]")
        
        # Show authorized users if configured
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            self.console.print(f"[dim]Authorized users: {', '.join(users_list)}[/dim]")
        
        self.console.print("\n[bold yellow]Starting SSH session...[/bold yellow]")
        self.console.print("[dim]Press Ctrl+C to return to menu[/dim]")
        
        # Build SSH command directly (like original handle_shell)
        ssh_command = ['ssh']
        
        # Add SSH key if specified
        if options['key']:
            ssh_command.extend(['-i', options['key']])
        
        # Add local port forwarding (-L)
        for forward in options['local_forward']:
            ssh_command.extend(['-L', forward])
        
        # Add remote port forwarding (-R)
        for forward in options['remote_forward']:
            ssh_command.extend(['-R', forward])
        
        # Add dynamic port forwarding (-D)
        if options['dynamic_forward']:
            ssh_command.extend(['-D', options['dynamic_forward']])
        
        # Add the target
        ssh_command.append(f'{ssh_user}@{public_hostname}')
        
        try:
            # Give a moment for user to read the info
            time.sleep(1)
            
            # Execute SSH command with terminal interaction (like original handle_shell)
            result = subprocess.run(ssh_command)
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[green]SSH session to {hostname} ended[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Error executing SSH command: {e}[/red]")
            self.pause()
    
    def handle_info_command(self):
        """Handle info command for selected agent"""
        if not self.selected_agent:
            self.console.print("[red]No agent selected! Use 'set <id>' first[/red]")
            self.pause()
            return
        
        self.handle_info(self.selected_agent)
    
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
    
    def show_agent_menu(self, agent: dict):
        """Show individual agent menu"""
        self.clear_screen()
        
        hostname = agent.get('hostname', 'Unknown')
        
        # Clean agent header without ASCII art
        agent_header = f"""[bold white]CHARIOT AGENT[/bold white] [dim white]│[/dim white] [bold {self.colors['accent']}]{{hostname}}[/bold {self.colors['accent']}]""".format(hostname=hostname)
        
        self.console.print(Panel(
            Align.center(agent_header),
            style=f"bold white on {self.colors['dark_sec']}",
            border_style=self.colors['primary'],
            padding=(1, 2),
            title="[bold]AGENT[/bold]",
            title_align="left"
        ))
        
        # Agent details
        self.show_agent_details(agent)
        
        # Professional actions menu
        health = agent.get('health_check', {})
        shell_available = health and health.get('cloudflared_status')
        
        if shell_available:
            shell_action = f"[bold {self.colors['success']}]s[/bold {self.colors['success']}] → Connect to shell [dim](tunnel available)[/dim]"
        else:
            shell_action = f"[{self.colors['dim']}]s → Shell unavailable (no tunnel)[/{self.colors['dim']}]"
        
        actions_panel = Panel(
            f"""[bold {self.colors['primary']}]Available Actions[/bold {self.colors['primary']}]

{shell_action}
[bold {self.colors['info']}]t[/bold {self.colors['info']}] → View and manage agent tasks
[bold {self.colors['secondary']}]i[/bold {self.colors['secondary']}] → Show detailed system information
[bold {self.colors['accent']}]b[/bold {self.colors['accent']}] → Return to main console""",
            border_style=self.colors['secondary'],
            padding=(1, 2),
            title="[dim]Actions[/dim]",
            title_align="left"
        )
        self.console.print(actions_panel)
        
        choice = self.get_input()
        
        if choice == 's' and shell_available:
            self.handle_shell(agent)
        elif choice == 't':
            self.handle_tasks(agent)
        elif choice == 'i':
            self.handle_info(agent)
        elif choice in ['b', 'back', '']:
            return
        else:
            self.console.print(f"[red]Invalid choice: {choice}[/red]")
            self.pause()
            self.show_agent_menu(agent)  # Recurse
    
    def show_agent_details(self, agent: dict):
        """Show professional agent details"""
        hostname = agent.get('hostname', 'Unknown')
        os_info = agent.get('os', 'unknown').title()
        os_version = agent.get('os_version', '')
        architecture = agent.get('architecture', 'Unknown')
        fqdn = agent.get('fqdn', 'N/A')
        client_id = agent.get('client_id', 'N/A')
        last_seen = agent.get('last_seen_at', 0)
        
        # Status
        if last_seen > 0:
            last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
            last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%Y-%m-%d %H:%M:%S UTC")
            status = f"[{self.colors['success']}]● ONLINE[/{self.colors['success']}]"
        else:
            last_seen_str = "Never"
            status = f"[{self.colors['error']}]○ OFFLINE[/{self.colors['error']}]"
        
        # System info table
        system_table = Table(
            title=f"[bold {self.colors['secondary']}]System Information[/bold {self.colors['secondary']}]",
            show_header=False, 
            box=None, 
            padding=(0, 3),
            border_style=self.colors['accent'],
            title_style=f"bold {self.colors['secondary']}"
        )
        system_table.add_column("Property", style=f"{self.colors['accent']}", width=16)
        system_table.add_column("Value", style="white")
        
        system_table.add_row("Status", status)
        system_table.add_row("Operating System", f"{os_info} {os_version}")
        system_table.add_row("Architecture", architecture)
        system_table.add_row("FQDN", fqdn)
        system_table.add_row("Client ID", client_id)
        system_table.add_row("Last Contact", last_seen_str)
        
        # Tunnel info
        health = agent.get('health_check', {})
        if health and health.get('cloudflared_status'):
            cf_status = health['cloudflared_status']
            tunnel_name = cf_status.get('tunnel_name', 'N/A')
            public_hostname = cf_status.get('hostname', 'N/A')
            authorized_users = cf_status.get('authorized_users', '').replace(',', ', ')
            
            system_table.add_row("", "")  # Spacer
            system_table.add_row("Tunnel Status", f"[{self.colors['warning']}]🔗 ACTIVE[/{self.colors['warning']}]")
            system_table.add_row("Tunnel Name", tunnel_name)
            system_table.add_row("Public Hostname", public_hostname)
            system_table.add_row("Authorized Users", authorized_users)
        else:
            system_table.add_row("", "")  # Spacer  
            system_table.add_row("Tunnel Status", f"[{self.colors['dim']}]⚬ Not configured[/{self.colors['dim']}]")
        
        system_panel = Panel(
            system_table,
            border_style=self.colors['accent'],
            padding=(1, 2)
        )
        self.console.print(system_panel)
    
    def handle_shell(self, agent: dict):
        """Handle shell connection"""
        import subprocess
        import sys
        
        hostname = agent.get('hostname', 'unknown')
        client_id = agent.get('client_id', 'N/A')
        
        # Check tunnel
        health = agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            self.console.print(f"[red]No Cloudflare tunnel available for {hostname}[/red]")
            self.pause()
            return
        
        # Get tunnel information
        cf_status = health['cloudflared_status']
        public_hostname = cf_status.get('hostname')
        authorized_users = cf_status.get('authorized_users', '')
        tunnel_name = cf_status.get('tunnel_name', 'N/A')
        
        if not public_hostname:
            self.console.print(f"[red]No public hostname found in tunnel configuration for {hostname}")
            self.pause()
            return
        
        # Show connection info
        self.console.print(f"[green]Connecting to {hostname} via {public_hostname}...[/green]")
        self.console.print(f"[dim]Tunnel: {tunnel_name}[/dim]")
        self.console.print(f"[dim]SSH user: {self.username}[/dim]")
        
        # Show authorized users if configured
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            self.console.print(f"[dim]Authorized users: {', '.join(users_list)}[/dim]")
        
        self.console.print("\n[bold yellow]Starting SSH session...[/bold yellow]")
        self.console.print("[dim]Press Ctrl+C to return to menu[/dim]")
        
        # Build SSH command using the current user's username
        ssh_command = ['ssh', f'{self.username}@{public_hostname}']
        
        try:
            # Give a moment for user to read the info
            import time
            time.sleep(1)
            
            # Execute SSH command with terminal interaction
            result = subprocess.run(ssh_command)
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[green]SSH session to {hostname} ended[/green]")
            
        except KeyboardInterrupt:
            self.console.print(f"\n[yellow]SSH connection to {hostname} interrupted[/yellow]")
        except FileNotFoundError:
            self.console.print("\n[red]Error: SSH command not found. Please ensure SSH is installed.[/red]")
        except Exception as e:
            self.console.print(f"\n[red]SSH connection failed: {e}[/red]")
        
        self.pause()
    
    def handle_tasks(self, agent: dict):
        """Handle agent tasks"""
        hostname = agent.get('hostname', 'unknown')
        self.console.print(f"[blue]Task management for {hostname}[/blue]")
        self.console.print("[dim]Task system implementation pending...[/dim]")
        self.pause()
    
    def handle_info(self, agent: dict):
        """Show detailed agent info"""
        self.clear_screen()
        hostname = agent.get('hostname', 'Unknown')
        
        self.console.print(Panel(
            f"[bold]Detailed Info: {hostname}[/bold]",
            style=f"on {self.colors['info']}"
        ))
        
        # Full agent data dump
        import json
        self.console.print(Panel(
            json.dumps(agent, indent=2),
            title="Raw Agent Data",
            border_style="dim"
        ))
        
        self.pause()
    
    def pause(self):
        """Professional pause with styling"""
        Prompt.ask(f"\n[{self.colors['dim']}]Press Enter to continue...[/{self.colors['dim']}]", default="")


def run_aegis_menu(sdk):
    """Run the Aegis menu interface"""
    menu = AegisMenu(sdk)
    menu.run()


