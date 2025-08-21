#!/usr/bin/env python3
"""
Aegis Menu Interface - Clean operator interface
Command-driven approach with tab completion and intuitive UX
"""

import os
import sys
import shlex
import gnureadline as readline

# Verbosity setting for Aegis UI (quiet by default)
VERBOSE = os.getenv('CHARIOT_AEGIS_VERBOSE') == '1'

from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.table import Table

from .menus import AegisStyle, MainMenu, AgentMenu
from .completion import CompletionManager


class AegisMenu:
    """Aegis menu interface with modern command-driven UX"""
    
    def __init__(self, sdk):
        self.sdk = sdk
        self.console = Console()
        self.verbose = VERBOSE
        self.agents = []
        self.selected_agent = None  # Currently selected agent
        self.ssh_count = 0
        self.last_agent_fetch = 0  # timestamp of last API call for caching
        self.agent_cache_duration = 60  # cache duration in seconds
        self._first_render = True
        
        # Get user information using the centralized, reliable method
        self.user_email, self.username = self.sdk.get_current_user()
        
        # Initialize style and menu components
        self.style = AegisStyle()
        self.colors = self.style.colors
        self.main_menu = MainMenu(self.style)
        self.agent_menu = AgentMenu(self.style)
        
        # Available commands for tab completion
        self.commands = [
            'set', 'ssh', 'info', 'list', 'job', 'reload', 'clear', 'help', 'quit', 'exit'
        ]
        
        # Initialize enhanced completion system
        self.completion_manager = CompletionManager(self)
        
        # Setup tab completion
        self.setup_tab_completion()
    
    def setup_tab_completion(self):
        """Setup enhanced readline tab completion using CompletionManager"""
        # Check if we have a real readline implementation
        if hasattr(readline, '__name__') and 'DummyReadline' in str(type(readline)):
            if self.verbose:
                print("Tab completion disabled - no readline support")
            return
        
        # Store completions to avoid regenerating them for each state
        self._cached_completions = []
        self._last_completion_line = ""
        
        def completer(text, state):
            try:
                # Get the current line and cursor position
                line = readline.get_line_buffer()
                begidx = readline.get_begidx()
                endidx = readline.get_endidx()
                
                # Only regenerate completions if line has changed
                if line != self._last_completion_line or state == 0:
                    self._cached_completions = self.completion_manager.get_completions(text, line, begidx, endidx)
                    self._last_completion_line = line
                
                # Return the appropriate completion for this state
                if state < len(self._cached_completions):
                    completion = self._cached_completions[state]
                    # Extract just the completion part (before any # comment)
                    return completion.split('  #')[0].strip()
                return None
                
            except Exception:
                # Fallback to basic command completion on error
                if state == 0:
                    basic_options = [cmd for cmd in self.commands if cmd.startswith(text)]
                    return basic_options[0] if basic_options else None
                return None
        
        # Set up readline completion
        readline.set_completer(completer)
        
        # Set up colored completion display
        self._setup_colored_completion_display()
        
        # Detect readline type and configure accordingly
        self._configure_readline_for_platform()
    
    def _setup_colored_completion_display(self):
        """Setup custom colored completion display"""
        try:
            # Check if we have a real readline implementation
            if hasattr(readline, '__name__') and 'DummyReadline' in str(type(readline)):
                return
            
            # Set completion display hook for colored output
            if hasattr(readline, 'set_completion_display_matches_hook'):
                def colored_completion_display(substitution, matches, longest_match_length):
                    """Custom completion display with colors"""
                    _ = substitution, longest_match_length  # Suppress unused parameter warnings
                    print()  # New line for cleaner display
                    
                    for match in matches:
                        # Parse the match to separate suggestion from description
                        if '  #' in match:
                            suggestion, description = match.split('  #', 1)
                            suggestion = suggestion.strip()
                            description = description.strip()
                            
                            # Apply colors using ANSI codes
                            colored_suggestion = f"\033[1m\033[38;5;61m{suggestion}\033[0m"
                            colored_description = f"\033[38;5;145m# {description}\033[0m"
                            
                            print(f"  {colored_suggestion}  {colored_description}")
                        else:
                            # Just the suggestion without description
                            suggestion = match.strip()
                            colored_suggestion = f"\033[1m\033[38;5;61m{suggestion}\033[0m"
                            print(f"  {colored_suggestion}")
                    
                    print()  # Add spacing after completions
                    
                    # Redraw the prompt
                    print(readline.get_line_buffer(), end='', flush=True)
                
                readline.set_completion_display_matches_hook(colored_completion_display)
                if self.verbose:
                    print("Custom colored completion display enabled")
                
        except Exception as e:
            if self.verbose:
                print(f"Could not enable colored completion display: {e}")
    
    def _configure_readline_for_platform(self):
        """Configure readline settings based on platform and readline type"""
        import platform
        
        system = platform.system()
        is_gnu_readline = hasattr(readline, '__name__') and 'gnu' in readline.__name__.lower()
        
        try:
            # Essential tab completion binding (works on all platforms)
            readline.parse_and_bind("tab: complete")
            
            if is_gnu_readline or system == "Linux":
                # GNU readline settings (Linux, or macOS with gnureadline)
                readline.parse_and_bind("set completion-ignore-case on")
                readline.parse_and_bind("set show-all-if-ambiguous on")
                readline.parse_and_bind("set show-all-if-unmodified on")
                readline.parse_and_bind("set page-completions off")
                readline.parse_and_bind("set completion-display-width 0")
                
                # Enable colored completions
                try:
                    readline.parse_and_bind("set colored-completion-prefix on")
                    readline.parse_and_bind("set colored-stats on")
                    readline.parse_and_bind("set visible-stats on")
                    if self.verbose:
                        print("Tab completion configured with GNU readline features + colors")
                except:
                    if self.verbose:
                        print("Tab completion configured with GNU readline features")
                
            elif system == "Darwin":  # macOS with BSD readline
                # BSD readline has limited configuration options
                try:
                    readline.parse_and_bind("set completion-ignore-case on")
                except:
                    pass
                if self.verbose:
                    print("Tab completion configured for macOS BSD readline")
                
            else:
                # Generic readline settings for other platforms
                try:
                    readline.parse_and_bind("set completion-ignore-case on")
                except:
                    pass
                if self.verbose:
                    print(f"Tab completion configured for {system}")
                
        except Exception:
            # Minimal fallback configuration
            try:
                readline.parse_and_bind("tab: complete")
                if self.verbose:
                    print("Basic tab completion enabled (limited features)")
            except:
                if self.verbose:
                    print("Failed to configure tab completion")
        
        # Set completion delimiters (characters that separate completion tokens)
        try:
            readline.set_completer_delims(' \t\n`~!@#$%^&*()=+[{]}\\|;:\'",<>?')
        except:
            pass
    
    def run(self):
        """Main interface loop"""
        self.clear_screen()
        self.reload_agents()
        
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
        try:
            self.agents = self.sdk.aegis.list()
            if self.verbose:
                self.console.print(f"[green]Loaded {len(self.agents)} agents successfully[/green]")
        except Exception as e:
            self.console.print(f"\n[red]Failed to load agents:[/red]")
            self.console.print(f"[red]  Error: {str(e)}[/red]")
            if 'network' in str(e).lower() or 'connection' in str(e).lower():
                self.console.print(f"[dim]  Check your network connection and API credentials[/dim]")
            elif 'auth' in str(e).lower():
                self.console.print(f"[dim]  Verify your authentication credentials[/dim]")
            else:
                self.console.print(f"[dim]  Try running 'reload' to retry[/dim]")
            self.console.print()
            self.agents = []
        
        # Refresh completion data when agents change
        self.completion_manager.refresh_completions()
    
    def get_selected_agent_context(self):
        """Get the selected agent context for commands"""
        return {
            'agent': self.selected_agent,
            'sdk': self.sdk,
            'client_id': self.selected_agent.client_id if self.selected_agent else None,
            'hostname': self.selected_agent.hostname if self.selected_agent else None
        }
    
    def has_selected_agent(self):
        """Check if an agent is currently selected"""
        return self.selected_agent is not None
    
    def require_selected_agent(self):
        """Return selected agent or display error message if none selected"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return None
        return self.selected_agent
    
    def call_sdk_with_agent(self, method_path, *args, **kwargs):
        """Call an SDK method using the selected agent context"""
        agent = self.require_selected_agent()
        if not agent:
            return None
        
        # Get the method from the SDK
        method = self.sdk
        for attr in method_path.split('.'):
            method = getattr(method, attr)
        
        # Call with agent context
        return method(agent, *args, **kwargs)
    
    def create_agents_table(self) -> Table:
        """Create a nicely formatted table of agents"""
        table = Table(show_header=True, header_style=f"bold {self.colors['primary']}")
        table.add_column("ID", style=f"{self.colors['accent']}", width=3)
        table.add_column("Hostname", style="bold white", width=20)
        table.add_column("Client ID", style=f"{self.colors['dim']}", width=12)
        table.add_column("OS", style=f"{self.colors['info']}", width=15)
        table.add_column("Status", width=8)
        table.add_column("Tunnel", width=6)
        
        for i, agent in enumerate(self.agents, 1):
            status_icon = "🟢" if agent.is_online else "🔴"
            tunnel_icon = "🔗" if agent.has_tunnel else "○"
            
            # Truncate long values for table display
            hostname = agent.hostname[:18] + '..' if len(agent.hostname) > 20 else agent.hostname
            client_id = agent.client_id[:10] + '..' if len(agent.client_id) > 12 else agent.client_id
            os_display = f"{agent.os} {agent.os_version}".strip()
            os_display = os_display[:13] + '..' if len(os_display) > 15 else os_display
            
            table.add_row(
                str(i),
                hostname,
                client_id,
                os_display,
                status_icon,
                tunnel_icon
            )
        
        return table

    def show_main_menu(self):
        """Show the main interface with reduced noise"""
        # Only show header on first render
        if self._first_render:
            current_account = self.sdk.keychain.account
            header = self.main_menu.get_enhanced_header(
                self.user_email, 
                self.username, 
                current_account
            )
            self.console.print(header)
            
            # Show simple help hint
            self.console.print(f"  [{self.colors['dim']}]hint: tab for completion • help for commands[/{self.colors['dim']}]\n")
        self._first_render = False
    
    def get_input(self) -> str:
        """Get user input with minimal context-aware prompt"""
        try:
            # Build minimal prompt
            if self.selected_agent:
                hostname = self.selected_agent.hostname or 'Unknown'
                # Don't truncate - just show hostname
                prompt = f"{hostname}> "
            else:
                prompt = "> "
            
            # Set readline prompt for proper display
            readline.set_startup_hook(lambda: readline.insert_text(""))
            
            # Get input with tab completion
            user_input = input(prompt).strip()
            return user_input
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C and Ctrl+D gracefully
            return "quit"
    
    def handle_choice(self, choice: str) -> bool:
        """Dead simple command dispatch"""
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
        
        command = args[0].lower()
        cmd_args = args[1:] if len(args) > 1 else []
        
        # Built-in TUI commands
        if command in ['q', 'quit', 'exit']:
            return False
            
        elif command in ['r', 'reload']:
            self.reload_agents(force_refresh=True)
            
        elif command == 'clear':
            self.clear_screen()
            
        elif command == 'set':
            self.handle_set(cmd_args)
            
        elif command in ['h', 'help']:
            self.handle_help(cmd_args)
            
        # CLI command delegation - direct SDK calls
        elif command == 'list':
            self.handle_list(cmd_args)
            
        elif command == 'ssh':
            self.handle_ssh(cmd_args)
            
        elif command == 'info':
            self.handle_info(cmd_args)
            
        elif command == 'job':
            self.handle_job(cmd_args)
            
        # Legacy support for direct numbers (backwards compatibility)
        elif command.isdigit():
            agent_num = int(command)
            if 1 <= agent_num <= len(self.agents):
                self.selected_agent = self.agents[agent_num - 1]
            else:
                self.console.print(f"\n  Invalid agent number: {agent_num}\n")
                self.pause()
                
        else:
            self.console.print(f"\n  Unknown command: {command}")
            self.console.print(f"  [{self.colors['dim']}]Type 'help' for available commands[/{self.colors['dim']}]\n")
            self.pause()
        
        return True
    
    # Simple handler methods - direct SDK calls
    def handle_set(self, args):
        """Handle set command - select an agent"""
        if not args:
            # Show available agents
            if not self.agents:
                self.console.print("\n  No agents available.\n")
                self.pause()
                return
            
            self.console.print("\n  Available agents:")
            for i, agent in enumerate(self.agents, 1):
                status = "🟢" if agent.is_online else "🔴"
                tunnel = "🔗" if agent.has_tunnel else ""
                self.console.print(f"    {i:2d}. {agent.hostname:<20} [{agent.client_id}] {status} {tunnel}")
            self.console.print()
            self.pause()
            return
        
        # Handle selection by client_id or number
        selection = args[0]
        if selection.isdigit():
            agent_num = int(selection)
            if 1 <= agent_num <= len(self.agents):
                self.selected_agent = self.agents[agent_num - 1]
                self.console.print(f"\n  Selected: {self.selected_agent.hostname}\n")
            else:
                self.console.print(f"\n  Invalid agent number: {agent_num}\n")
                self.pause()
        else:
            # Try to find by client_id
            try:
                agent = self.sdk.aegis.get_by_client_id(selection)
                if agent:
                    self.selected_agent = agent
                    self.console.print(f"\n  Selected: {agent.hostname}\n")
                else:
                    self.console.print(f"\n[red]  Agent not found:[/red] {selection}")
                    self.console.print(f"[dim]  Use 'list' to see available agents or 'set' without arguments for options[/dim]\n")
                    self.pause()
            except Exception as e:
                self.console.print(f"\n[red]  Error selecting agent:[/red] {selection}")
                self.console.print(f"[red]  {str(e)}[/red]")
                self.console.print(f"[dim]  Use 'list' to see available agents or 'set' without arguments for options[/dim]\n")
                self.pause()
    
    def handle_help(self, args):
        """Handle help command"""
        if args and args[0] in ['ssh', 'list', 'info', 'job', 'set']:
            help_text = self.completion_manager.get_help_text(args[0])
            self.console.print(help_text)
            self.pause()
        else:
            self.console.print("\n  Available commands:")
            self.console.print("    set <id>        - Select an agent")
            self.console.print("    list [--details] [--filter <text>] - List agents")
            self.console.print("    ssh [options]   - SSH to selected agent")
            self.console.print("    info            - Show selected agent info")
            self.console.print("    job [capabilities] - Run job on selected agent")
            self.console.print("    reload          - Refresh agent list")
            self.console.print("    help            - Show this help")
            self.console.print("    quit/exit       - Exit")
            self.console.print()
            self.pause()
    
    def handle_list(self, args):
        """Handle list command - direct SDK call"""
        details = '--details' in args
        filter_text = None
        
        # Simple argument parsing
        if '--filter' in args:
            try:
                idx = args.index('--filter')
                if idx + 1 < len(args):
                    filter_text = args[idx + 1]
            except (IndexError, ValueError):
                pass
        
        try:
            result = self.sdk.aegis.format_agents_list(details=details, filter_text=filter_text)
            self.console.print(result)
            self.console.print()
            self.pause()
        except Exception as e:
            self.console.print(f"[red]Error listing agents: {e}[/red]")
            self.pause()
    
    def handle_ssh(self, args):
        """Handle ssh command - direct SDK call"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        # Parse SSH options
        user = None
        local_forward = []
        remote_forward = []
        dynamic_forward = None
        key = None
        ssh_opts = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ['-u', '--user'] and i + 1 < len(args):
                user = args[i + 1]
                i += 2
            elif arg in ['-L', '--local-forward'] and i + 1 < len(args):
                local_forward.append(args[i + 1])
                i += 2
            elif arg in ['-R', '--remote-forward'] and i + 1 < len(args):
                remote_forward.append(args[i + 1])
                i += 2
            elif arg in ['-D', '--dynamic-forward'] and i + 1 < len(args):
                dynamic_forward = args[i + 1]
                i += 2
            elif arg in ['-i', '--key'] and i + 1 < len(args):
                key = args[i + 1]
                i += 2
            elif arg == '--ssh-opts' and i + 1 < len(args):
                ssh_opts = args[i + 1]
                i += 2
            else:
                i += 1
        
        try:
            self.sdk.aegis.ssh_to_agent(
                agent=self.selected_agent,
                user=user,
                local_forward=local_forward,
                remote_forward=remote_forward,
                dynamic_forward=dynamic_forward,
                key=key,
                ssh_opts=ssh_opts,
                display_info=True
            )
        except Exception as e:
            self.console.print(f"[red]SSH error: {e}[/red]")
            self.pause()
    
    def handle_info(self, args):
        """Handle info command - direct SDK call"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        try:
            self.console.print(self.selected_agent.to_detailed_string())
            self.console.print()
            self.pause()
        except Exception as e:
            self.console.print(f"[red]Error getting agent info: {e}[/red]")
            self.pause()
    
    def handle_job(self, args):
        """Handle job command - direct SDK call"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        # Parse capabilities and config
        capabilities = []
        config = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ['-c', '--capability'] and i + 1 < len(args):
                capabilities.append(args[i + 1])
                i += 2
            elif arg == '--config' and i + 1 < len(args):
                config = args[i + 1]
                i += 2
            else:
                # Treat as capability if no flag
                capabilities.append(arg)
                i += 1
        
        try:
            result = self.sdk.aegis.run_job(
                agent=self.selected_agent,
                capabilities=capabilities if capabilities else None,
                config=config
            )
            
            if 'capabilities' in result:
                self.console.print("Available capabilities:")
                for cap in result['capabilities']:
                    name = cap.get('name', 'unknown')
                    desc = cap.get('description', '')[:50]
                    self.console.print(f"  {name:<25} {desc}")
            elif result.get('success'):
                self.console.print(f"✓ Job queued successfully")
                self.console.print(f"  Job ID: {result.get('job_id', 'unknown')}")
                self.console.print(f"  Status: {result.get('status', 'unknown')}")
            else:
                self.console.print(f"Error: {result.get('message', 'Unknown error')}")
            
            self.console.print()
            self.pause()
        except Exception as e:
            self.console.print(f"[red]Job error: {e}[/red]")
            self.pause()
    
    def pause(self):
        """Professional pause with styling"""
        if self.verbose:
            Prompt.ask(f"\n[{self.colors['dim']}]Press Enter to continue...[/{self.colors['dim']}]")
        # Quiet mode: do not block


def run_aegis_menu(sdk):
    """Run the Aegis menu interface"""
    menu = AegisMenu(sdk)
    menu.run()