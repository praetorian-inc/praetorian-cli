#!/usr/bin/env python3
"""
Aegis Menu Interface - Ultra-fast, clean operator interface
Command-driven approach with tab completion and intuitive UX
"""

import os
import sys
import shlex

# Handle readline import for different platforms
try:
    # Try to import gnureadline first (better compatibility on macOS)
    import gnureadline as readline
    print("✅ Using GNU readline for enhanced completion")
except ImportError:
    try:
        # Fallback to standard readline
        import readline
        print("⚠️  Using standard readline (limited completion on macOS)")
    except ImportError:
        # Create a dummy readline for systems without it
        class DummyReadline:
            def set_completer(self, func): pass
            def parse_and_bind(self, string): pass
            def get_line_buffer(self): return ""
            def get_begidx(self): return 0
            def get_endidx(self): return 0
        
        readline = DummyReadline()
        print("❌ No readline available - tab completion disabled")

from rich.console import Console
from rich.prompt import Prompt

from .commands import SetCommand, SSHCommand, InfoCommand, ListCommand, HelpCommand, TasksCommand
from .menus import AegisStyle, MainMenu, AgentMenu
from .completion import CompletionManager


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
        
        # Initialize enhanced completion system
        self.completion_manager = CompletionManager(self)
        
        # Setup tab completion
        self.setup_tab_completion()
    
    def setup_tab_completion(self):
        """Setup enhanced readline tab completion using CompletionManager"""
        # Check if we have a real readline implementation
        if hasattr(readline, '__name__') and 'DummyReadline' in str(type(readline)):
            print("⚠️  Tab completion disabled - no readline support")
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
                print("✅ Custom colored completion display enabled")
                
        except Exception as e:
            print(f"⚠️  Could not enable colored completion display: {e}")
    
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
                    print("✅ Tab completion configured with GNU readline features + colors")
                except:
                    print("✅ Tab completion configured with GNU readline features")
                
            elif system == "Darwin":  # macOS with BSD readline
                # BSD readline has limited configuration options
                try:
                    readline.parse_and_bind("set completion-ignore-case on")
                except:
                    pass
                print("✅ Tab completion configured for macOS BSD readline")
                
            else:
                # Generic readline settings for other platforms
                try:
                    readline.parse_and_bind("set completion-ignore-case on")
                except:
                    pass
                print(f"✅ Tab completion configured for {system}")
                
        except Exception:
            # Minimal fallback configuration
            try:
                readline.parse_and_bind("tab: complete")
                print("⚠️  Basic tab completion enabled (limited features)")
            except:
                print("❌ Failed to configure tab completion")
        
        # Set completion delimiters (characters that separate completion tokens)
        try:
            readline.set_completer_delims(' \t\n`~!@#$%^&*()=+[{]}\\|;:\'",<>?')
        except:
            pass
    
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
        # Refresh completion data when agents change
        self.completion_manager.refresh_completions()

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
            # Check for specific help requests (e.g., "help ssh", "ssh --help")
            if len(args) > 1:
                help_topic = args[1].lower()
                help_text = self.completion_manager.get_help_text(help_topic)
                self.console.print(help_text)
                self.pause()
            else:
                self.help_cmd.execute()
            
        elif command == 'list':
            self.list_cmd.execute()
            
        elif command == 'set':
            if len(args) >= 2 and (args[1] == '--help' or args[1] == '-h'):
                help_text = self.completion_manager.get_help_text('set')
                self.console.print(help_text)
                self.pause()
            elif len(args) < 2:
                self.set_cmd.execute([])
            else:
                self.set_cmd.execute([args[1]])
                
        elif command == 'ssh':
            ssh_args = args[1:] if len(args) > 1 else []
            # Handle --help flag
            if '--help' in ssh_args or '-h' in ssh_args:
                help_text = self.completion_manager.get_help_text('ssh')
                self.console.print(help_text)
                self.pause()
            else:
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