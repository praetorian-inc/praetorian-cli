#!/usr/bin/env python3
"""
Aegis Menu Interface - Ultra-fast, clean operator interface
Command-driven approach with tab completion and intuitive UX
"""

import os
import sys
import readline
import shlex

from rich.console import Console
from rich.prompt import Prompt

from .commands import SetCommand, SSHCommand, InfoCommand, ListCommand, HelpCommand, TasksCommand
from .menus import AegisStyle, MainMenu, AgentMenu


class AegisMenu:
    """Ultra-fast Aegis menu interface with modern command-driven UX"""
    
    def __init__(self, sdk):
        self.sdk = sdk
        self.console = Console()
        self.agents = []
        self.selected_agent = None  # Currently selected agent
        self.ssh_count = 0
        self.last_agent_fetch = 0  # timestamp of last API call for caching
        self.agent_cache_duration = 60  # cache duration in seconds
        
        # Get user information using the centralized, reliable method
        self.user_email, self.username = self.sdk.get_current_user()
        
        # Initialize style and menu components
        self.style = AegisStyle()
        self.colors = self.style.colors
        self.main_menu = MainMenu(self.style)
        self.agent_menu = AgentMenu(self.style)
        
        # Available commands for tab completion
        self.commands = [
            'set', 'ssh', 'info', 'list', 'reload', 'clear', 'help', 'quit', 'exit'
        ]
        
        # Initialize command handlers
        self.set_cmd = SetCommand(self)
        self.ssh_cmd = SSHCommand(self)
        self.info_cmd = InfoCommand(self)
        self.list_cmd = ListCommand(self)
        self.help_cmd = HelpCommand(self)
        self.tasks_cmd = TasksCommand(self)
        
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
        self.list_cmd.load_agents()
        
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
    
    def reload_agents(self, force_refresh=True):
        """Load agents with 60-second caching and compute status properties"""
        self.list_cmd.load_agents(force_refresh=force_refresh)

    def show_main_menu(self):
        """Show the main interface"""
        # Show header
        current_account = self.sdk.keychain.account
        header_panel = self.main_menu.get_header_panel(
            self.user_email, 
            self.username, 
            current_account
        )
        self.console.print(header_panel)
        self.console.print()
        
        # Show commands panel
        selected_info = self.main_menu.get_selected_agent_info(self.selected_agent)
        cmd_panel = self.main_menu.get_commands_panel(
            self.ssh_count, 
            len(self.agents), 
            selected_info
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
            self.reload_agents(force_refresh=True)
            self.console.print("[green]Agent list reloaded![/green]")
            
        elif command == 'clear':
            self.clear_screen()
            
        elif command in ['h', 'help']:
            self.help_cmd.execute()
            
        elif command == 'list':
            self.list_cmd.execute()
            
        elif command == 'set':
            if len(args) < 2:
                self.set_cmd.execute([])
            else:
                self.set_cmd.execute([args[1]])
                
        elif command == 'ssh':
            ssh_args = args[1:] if len(args) > 1 else []
            self.ssh_cmd.execute(ssh_args)
            
        elif command == 'info':
            self.info_cmd.execute()
            
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
    
    def show_agent_menu(self, agent: dict):
        """Show individual agent menu"""
        self.clear_screen()
        
        hostname = agent.get('hostname', 'Unknown')
        
        # Show agent header
        header_panel = self.agent_menu.get_agent_header_panel(hostname)
        self.console.print(header_panel)
        
        # Agent details
        self.info_cmd.show_agent_details(agent)
        
        # Show actions panel
        health = agent.get('health_check', {})
        shell_available = health and health.get('cloudflared_status')
        
        actions_panel = self.agent_menu.get_actions_panel(shell_available)
        self.console.print(actions_panel)
        
        choice = self.get_input()
        
        if choice == 's' and shell_available:
            self.ssh_cmd.handle_shell(agent)
        elif choice == 't':
            self.tasks_cmd.handle_tasks(agent)
        elif choice == 'i':
            self.info_cmd.handle_info(agent)
        elif choice in ['b', 'back', '']:
            return
        else:
            self.console.print(f"[red]Invalid choice: {choice}[/red]")
            self.pause()
            self.show_agent_menu(agent)  # Recurse

    def pause(self):
        """Professional pause with styling"""
        Prompt.ask(f"\n[{self.colors['dim']}]Press Enter to continue...[/{self.colors['dim']}]", default="")


def run_aegis_menu(sdk):
    """Run the Aegis menu interface"""
    menu = AegisMenu(sdk)
    menu.run()