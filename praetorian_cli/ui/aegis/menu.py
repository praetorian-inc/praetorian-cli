#!/usr/bin/env python3
"""
Aegis Menu Interface - Clean operator interface
Command-driven approach with intuitive UX
"""

import os
import shlex

# Verbosity setting for Aegis UI (quiet by default)
VERBOSE = os.getenv('CHARIOT_AEGIS_VERBOSE') == '1'

from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL

from .utils import (
    relative_time, safe_get_attr, format_job_status, format_os_display,
    format_timestamp, compute_agent_groups, get_agent_display_style,
    parse_agent_identifier, truncate_text
)


class AegisMenu:
    """Aegis menu interface with modern command-driven UX"""
    
    def __init__(self, sdk):
        self.sdk = sdk
        self.console = Console()
        self.verbose = VERBOSE
        self.agents = []
        self.selected_agent = None  
        self.ssh_count = 0
        self.last_agent_fetch = 0  
        self.agent_cache_duration = 60  
        self._first_render = True
        self.agent_computed_data = {}  
        self.current_prompt = "> " 
        
        self.user_email, self.username = self.sdk.get_current_user()
        
        # Define Praetorian color scheme
        self.colors = {
            'primary': '#4A90E2',
            'success': '#7ED321', 
            'warning': '#F5A623',
            'error': '#D0021B',
            'info': '#50E3C2',
            'accent': '#BD10E0',
            'dim': '#9B9B9B'
        }
        
        self.commands = [
            'set', 'ssh', 'info', 'list', 'job', 'reload', 'clear', 'help', 'quit', 'exit'
        ]

        # Initialize very simple autocomplete (Tab completion)
        self._init_autocomplete()
    
    
    def run(self):
        """Main interface loop"""
        self.clear_screen()
        self.reload_agents()
        
        if self.agents:
            self.show_agents_list()
        
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
    
    def reload_agents(self, force_refresh: bool = False):    
        """Load agents with 60-second caching and compute status properties"""
        self.load_agents()
        
        if self.verbose and self.agents:
            self.console.print(f"[green]Loaded {len(self.agents)} agents successfully[/green]")
        
    
    def get_selected_agent_context(self):
        """Get the selected agent context for commands"""
        return {
            'agent': self.selected_agent,
            'sdk': self.sdk,
            'client_id': self.selected_agent.client_id if self.selected_agent else None,
            'hostname': self.selected_agent.hostname if self.selected_agent else None
        }
    
    def require_selected_agent(self):
        """Return selected agent or display error message if none selected"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return None
        return self.selected_agent
    
    def _compute_agent_status(self):
        """Compute agent status data and groupings using utility function"""
        current_time = datetime.now().timestamp()
        self.agent_computed_data = compute_agent_groups(self.agents, current_time)
    
    def show_agents_list(self, show_offline=False):
        """Compose and display the agents table using pre-computed properties"""
        if not self.agents:
            self.console.print(f"  [{self.colors['warning']}]No agents available[/{self.colors['warning']}]")
            self.console.print(f"  [{self.colors['dim']}]Press 'r <Enter>' to reload[/{self.colors['dim']}]")
            return
        
        self._compute_agent_status()
        
        active_tunnel_agents = self.agent_computed_data.get('active_tunnel')
        online_agents = self.agent_computed_data.get('online')
        offline_agents = self.agent_computed_data.get('offline')
        
        display_agents = active_tunnel_agents + online_agents
        if show_offline:
            display_agents = display_agents + offline_agents
        
        self.console.print()

        if not display_agents:
            if offline_agents:
                self.console.print(f"  No agents online\n")
                self.console.print(f"  [{self.colors['dim']}]• {len(offline_agents)} agents are offline[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Use 'list --all' to see them[/{self.colors['dim']}]")
            else:
                self.console.print(f"  No agents found\n")
                self.console.print(f"  [{self.colors['dim']}]• Check your network connection[/{self.colors['dim']}]")
                self.console.print(f"  [{self.colors['dim']}]• Verify agents are running[/{self.colors['dim']}]")
            self.console.print(f"  [{self.colors['dim']}]• Use 'reload' to refresh[/{self.colors['dim']}]")
            self.console.print()
            return
        
        status_parts = []
        if active_tunnel_agents:
            status_parts.append(f"{len(active_tunnel_agents)} tunneled")
        if online_agents:
            status_parts.append(f"{len(online_agents)} online")
        if offline_agents and not show_offline:
            status_parts.append(f"[{self.colors['dim']}]{len(offline_agents)} hidden[/{self.colors['dim']}]")
        elif offline_agents:
            status_parts.append(f"[{self.colors['dim']}]{len(offline_agents)} offline[/{self.colors['dim']}]")
        
        if status_parts:
            self.console.print("  " + "   ".join(status_parts))
        
        self.console.print()
        table = Table(
            show_header=True,
            header_style=f"{self.colors['dim']}",
            border_style=self.colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )
        
        table.add_column("", style=f"{self.colors['dim']}", width=4, justify="right", no_wrap=True)
        table.add_column("HOSTNAME", style="white", min_width=25, no_wrap=False)
        table.add_column("OS", style=f"{self.colors['dim']}", width=16, no_wrap=True)
        table.add_column("STATUS", width=8, justify="left", no_wrap=True)
        table.add_column("TUNNEL", width=7, justify="left", no_wrap=True)
        table.add_column("SEEN", style=f"{self.colors['dim']}", width=10, justify="right", no_wrap=True)
        
        for i, (agent_idx, agent) in enumerate(display_agents, 1):
            hostname = safe_get_attr(agent, 'hostname', 'Unknown')
            os_info = safe_get_attr(agent, 'os', 'unknown')
            os_version = safe_get_attr(agent, 'os_version', '')
            os_display = format_os_display(os_info, os_version)
            
            # Determine group based on agent properties
            if agent.is_online and getattr(agent, 'has_tunnel', False):
                group = 'active_tunnel'
            elif agent.is_online:
                group = 'online'
            else:
                group = 'offline'
            
            # Get display styles from utility function
            styles = get_agent_display_style(group, self.colors)
            status = styles['status']
            tunnel = styles['tunnel']
            idx_style = styles['idx_style']
            hostname_style = styles['hostname_style']
            
            # Compute last seen time
            current_time = datetime.now().timestamp()
            if agent.last_seen_at > 0 and agent.is_online:
                last_seen = relative_time(agent.last_seen_at / 1000000 if agent.last_seen_at > 1000000000000 else agent.last_seen_at, current_time)
            else:
                last_seen = "—"
            
            table.add_row(
                Text(str(i), style=idx_style),
                Text(hostname, style=hostname_style),
                os_display,
                status,
                tunnel,
                last_seen
            )
        
        self.console.print(table)
        self.console.print()

    def show_main_menu(self):
        """Show the main interface with reduced noise"""
        if self._first_render:
            current_account = self.sdk.keychain.account
            
            # Simple header without external class dependency
            self.console.print(f"\n[bold {self.colors['primary']}]Aegis Agent Interface[/bold {self.colors['primary']}]")
            self.console.print(f"  [{self.colors['dim']}]User: {self.username} | Account: {current_account}[/{self.colors['dim']}]")
            self.console.print(f"  [{self.colors['dim']}]hint: type 'help' for commands[/{self.colors['dim']}]\n")
            
        self._first_render = False
    
    def get_input(self) -> str:
        """Get user input with minimal context-aware prompt"""
        try:
            if self.selected_agent:
                hostname = safe_get_attr(self.selected_agent, 'hostname', 'Unknown')
                self.current_prompt = f"{hostname}> "
            else:
                self.current_prompt = "> "
            
            user_input = input(self.current_prompt).strip()
            return user_input
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C and Ctrl+D gracefully
            return "quit"

    # --- Autocomplete -----------------------------------------------------
    def _init_autocomplete(self):
        """Attach a minimal Tab-completion using readline when available."""
        try:
            import readline  # type: ignore
        except Exception:
            self._readline = None
            return

        self._readline = readline

        # Configure basic word delimiters (keep common shell delimiters)
        try:
            delims = readline.get_completer_delims()
            # Allow hyphenated options and slashes to be part of a word
            for ch in "-/.":
                delims = delims.replace(ch, "")
            readline.set_completer_delims(delims)
        except Exception:
            pass

        def completer(text, state):
            try:
                buf = readline.get_line_buffer()
                beg = getattr(readline, 'get_begidx', lambda: len(buf))()
                # Portion before the current word being completed
                before = buf[:beg]
                try:
                    tokens = shlex.split(before)
                except Exception:
                    tokens = before.split()

                # If starting fresh or completing the first token
                if not tokens:
                    options = [c for c in self.commands if c.startswith(text)]
                else:
                    cmd = tokens[0]

                    # If still typing the command itself (no space yet)
                    if len(tokens) == 1 and not before.endswith(' '):
                        options = [c for c in self.commands if c.startswith(text)]
                    else:
                        options = self._autocomplete_options_for(cmd, text, tokens)

                # Ensure distinct, sorted for stable cycling
                options = sorted(set(options))
                return options[state] if state < len(options) else None
            except Exception:
                return None

        # On macOS, readline is usually libedit; Tab is still the default.
        try:
            self._readline.set_completer(completer)
            doc = getattr(self._readline, "__doc__", "") or ""
            if "libedit" in doc.lower():
                # macOS default: libedit compatibility layer
                self._readline.parse_and_bind("bind ^I rl_complete")
            else:
                # GNU readline
                self._readline.parse_and_bind('tab: complete')
        except Exception:
            pass

    def _autocomplete_options_for(self, cmd, text, tokens):
        """Return simple context-aware options for completion."""
        # Top-level fallbacks
        if cmd in ['quit', 'exit', 'clear', 'reload', 'info']:
            return []

        if cmd == 'help':
            return [c for c in self.commands if c.startswith(text)]

        if cmd == 'list':
            opts = ['--all', '-a']
            return [o for o in opts if o.startswith(text)]

        if cmd == 'set':
            # Offer indices, hostnames, and client_ids
            suggestions = []
            try:
                # Indices start at 1 in the UI table
                for idx, agent in enumerate(self.agents or [], 1):
                    hostname = safe_get_attr(agent, 'hostname', None)
                    client_id = getattr(agent, 'client_id', None)
                    suggestions.append(str(idx))
                    if hostname:
                        suggestions.append(str(hostname))
                    if client_id:
                        suggestions.append(str(client_id))
            except Exception:
                pass
            return [s for s in suggestions if s and s.startswith(text)]

        if cmd == 'job':
            sub = ['list', 'run', 'capabilities', 'caps']
            # If only 'job ' entered, suggest subcommands
            if len(tokens) <= 2:
                return [s for s in sub if s.startswith(text)]
            # Minimal: do not attempt to complete capability names here
            return []

        if cmd == 'ssh':
            ssh_opts = [
                '-u', '--user',
                '-L', '--local-forward',
                '-R', '--remote-forward',
                '-D', '--dynamic-forward',
                '-i', '--key',
                '--ssh-opts'
            ]
            return [o for o in ssh_opts if o.startswith(text)]

        # Default: no suggestions
        return []
    
    def handle_choice(self, choice: str) -> bool:
        """Dead simple command dispatch"""
        if not choice:
            return True  # Just refresh
        
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
            
        elif command == 'list':
            self.handle_list(cmd_args)
            
        elif command == 'ssh':
            self.handle_ssh(cmd_args)
            
        elif command == 'info':
            self.handle_info(cmd_args)
            
        elif command == 'job':
            self.handle_job(cmd_args)
                
        else:
            self.console.print(f"\n  Unknown command: {command}")
            self.console.print(f"  [{self.colors['dim']}]Type 'help' for available commands[/{self.colors['dim']}]\n")
            self.pause()
        
        return True
    
    def handle_set(self, args):
        """Handle set command - select an agent using utility function"""
        if not args:
            self.console.print(f"\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        selection = args[0]
        selected_agent = parse_agent_identifier(selection, self.agents)
        
        if selected_agent:
            self.selected_agent = selected_agent
            hostname = safe_get_attr(selected_agent, 'hostname', 'Unknown')
            self.console.print(f"\n  Selected: {hostname}\n")
        else:
            self.console.print(f"\n[red]  Agent not found:[/red] {selection}")
            self.console.print(f"[dim]  Use agent number (1-{len(self.agents)}), client ID, or hostname[/dim]\n")
            self.pause()
    
    def handle_help(self, args):
        """Handle help command"""
        if args and args[0] in ['ssh', 'list', 'info', 'job', 'set']:
            # Simple command-specific help (can be expanded later)
            self.console.print(f"\nHelp for '{args[0]}' command - see main help for details\n")
            self.pause()
        else:
            commands_table = Table(
                show_header=True,
                header_style=f"bold {self.colors['primary']}",
                border_style=self.colors['dim'],
                box=MINIMAL,
                show_lines=False,
                padding=(0, 2),
                pad_edge=False
            )
            
            commands_table.add_column("COMMAND", style=f"bold {self.colors['success']}", min_width=20, no_wrap=True)
            commands_table.add_column("DESCRIPTION", style="white", no_wrap=False)
            
            commands_table.add_row("set <id>", "Select an agent by number, client_id, or hostname")
            commands_table.add_row("list [--all]", "List online agents (--all shows offline too)")
            commands_table.add_row("ssh [options]", "SSH to selected agent with port forwarding")
            commands_table.add_row("info", "Show detailed information for selected agent")
            commands_table.add_row("job list", "List recent jobs for selected agent")
            commands_table.add_row("job capabilities [--details]", "List available capabilities")
            commands_table.add_row("job run <capability>", "Run capability on selected agent")
            commands_table.add_row("reload", "Refresh agent list from server")
            commands_table.add_row("help [command]", "Show this help or command-specific help")
            commands_table.add_row("clear", "Clear terminal screen")
            commands_table.add_row("quit / exit", "Exit the interface")
            
            self.console.print()
            self.console.print("  Available Commands")
            self.console.print()
            self.console.print(commands_table)
            
            examples_table = Table(
                show_header=True,
                header_style=f"bold {self.colors['warning']}",
                border_style=self.colors['dim'],
                box=MINIMAL,
                show_lines=False,
                padding=(0, 2),
                pad_edge=False
            )
            
            examples_table.add_column("EXAMPLE", style=f"bold {self.colors['accent']}", min_width=25, no_wrap=True)
            examples_table.add_column("DESCRIPTION", style=f"{self.colors['dim']}", no_wrap=False)
            
            examples_table.add_row("set 1", "Select first agent")
            examples_table.add_row("set abc", "Select agent by hostname")
            examples_table.add_row("ssh -D 1080", "SSH with SOCKS proxy on port 1080")
            examples_table.add_row("list --all", "Show all agents including offline")
            examples_table.add_row("job list", "List recent jobs")
            examples_table.add_row("job capabilities", "List available capabilities")
            examples_table.add_row("job caps --details", "Show full capability descriptions")
            examples_table.add_row("job run windows-enum", "Run capability on selected agent")
            
            self.console.print()
            self.console.print("  Examples")
            self.console.print()
            self.console.print(examples_table)
            self.console.print()
            self.pause()
    
    def handle_list(self, args):
        """Handle list command using sophisticated table rendering"""
        show_offline = '--all' in args or '-a' in args
        
        if not self.agents:
            self.load_agents()
            
        self.show_agents_list(show_offline=show_offline)
        self.pause()
    
    def load_agents(self):
        """Load agents from SDK"""
        try:
            with self.console.status(
                f"[{self.colors['dim']}]Loading agents...[/{self.colors['dim']}]",
                spinner="dots",
                spinner_style=f"{self.colors['primary']}"
            ):
                self.agents = self.sdk.aegis.list() or []
                self.last_agent_fetch = datetime.now().timestamp()
                
            if self.verbose or not self.agents:
                agent_count = len(self.agents)
                if agent_count > 0:
                    self.console.print(f"[green]✓ Loaded {agent_count} agents[/green]")
                else:
                    self.console.print(f"[yellow]⚠ No agents found[/yellow]")
                    
        except Exception as e:
            self.console.print(f"[red]✗ Error loading agents: {e}[/red]")
            self.agents = []
    
    def handle_ssh(self, args):
        """Handle ssh command - direct SDK call"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
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
        """Handle job command with subcommands: list, run, capabilities"""
        if not args:
            self.show_job_help()
            return
        
        subcommand = args[0].lower()
        
        if subcommand == 'list':
            self.list_jobs()
        elif subcommand == 'run':
            self.run_job(args[1:])
        elif subcommand == 'capabilities' or subcommand == 'caps':
            self.list_capabilities(args[1:])
        else:
            self.console.print(f"\n  Unknown job subcommand: {subcommand}")
            self.show_job_help()
    
    def show_job_help(self):
        """Show job command help"""
        help_text = f"""
  Job Commands

  job list                  List recent jobs for selected agent
  job run <capability>      Run a capability on selected agent
                           [--config <json>] Optional configuration  
  job capabilities          List available capabilities (alias: caps)
                           [--details] Show full descriptions
  
  Examples:
    job list                 # List recent jobs
    job capabilities         # List capabilities with brief descriptions
    job caps --details       # List capabilities with full descriptions  
    job run windows-enum     # Run capability on selected agent
    job run smb-enum --config '{{"target":"192.168.1.1"}}'
"""
        self.console.print(help_text)
        self.pause()
    
    def list_jobs(self):
        """List recent jobs for the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        hostname = safe_get_attr(self.selected_agent, 'hostname', 'Unknown')
        
        try:
            # Get recent jobs for this agent
            jobs, _ = self.sdk.jobs.list(prefix_filter=hostname)
            
            if not jobs:
                self.console.print(f"\n  No jobs found for {hostname}\n")
                self.pause()
                return
            
            # Sort by creation time and show recent ones
            jobs.sort(key=lambda j: j.get('created', 0), reverse=True)
            
            # Create jobs table
            jobs_table = Table(
                show_header=True,
                header_style=f"bold {self.colors['primary']}",
                border_style=self.colors['dim'],
                box=MINIMAL,
                show_lines=False,
                padding=(0, 2),
                pad_edge=False
            )
            
            jobs_table.add_column("JOB ID", style=f"bold {self.colors['accent']}", width=12, no_wrap=True)
            jobs_table.add_column("CAPABILITY", style="white", min_width=20, no_wrap=True)
            jobs_table.add_column("STATUS", width=10, justify="center", no_wrap=True)
            jobs_table.add_column("CREATED", style=f"{self.colors['dim']}", width=12, justify="right", no_wrap=True)
            
            self.console.print()
            self.console.print(f"  Recent Jobs for {hostname}")
            self.console.print()
            
            for job in jobs[:10]:  # Show last 10 jobs
                capability = job.get('capabilities', ['unknown'])[0] if job.get('capabilities') else 'unknown'
                status = job.get('status', 'unknown')
                job_id = job.get('key', '').split('#')[-1][:10]
                created = job.get('created', 0)
                
                # Format creation time using utility function
                created_str = format_timestamp(created)
                
                # Format status using utility function
                status_display = format_job_status(status, self.colors)
                
                jobs_table.add_row(job_id, capability, status_display, created_str)
            
            self.console.print(jobs_table)
            self.console.print()
            self.pause()
            
        except Exception as e:
            self.console.print(f"[red]Error listing jobs: {e}[/red]")
            self.pause()
    
    def run_job(self, args):
        """Run a capability on the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        if not args:
            self.console.print("\n[red]  Usage: job run <capability> [--config <json>][/red]")
            self.console.print("  Use 'job capabilities' to see available capabilities\n")
            self.pause()
            return
        
        capability = args[0]
        config = None
        
        # Parse config option
        i = 1
        while i < len(args):
            if args[i] == '--config' and i + 1 < len(args):
                config = args[i + 1]
                i += 2
            else:
                i += 1
        
        try:
            result = self.sdk.aegis.run_job(
                agent=self.selected_agent,
                capabilities=[capability],
                config=config
            )
            
            if result.get('success'):
                self.console.print(f"\n[green]✓ Job queued successfully[/green]")
                self.console.print(f"  Capability: {capability}")
                if 'job_id' in result:
                    self.console.print(f"  Job ID: {result['job_id']}")
                if 'status' in result:
                    self.console.print(f"  Status: {result['status']}")
            else:
                error_msg = result.get('message', 'Unknown error')
                self.console.print(f"\n[red]Error running job: {error_msg}[/red]")
            
            self.console.print()
            self.pause()
        except Exception as e:
            self.console.print(f"[red]Job execution error: {e}[/red]")
            self.pause()
    
    def list_capabilities(self, args):
        """List available capabilities for the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            self.pause()
            return
        
        show_details = '--details' in args or '-d' in args
        
        try:
            # Request capabilities list from SDK
            result = self.sdk.aegis.run_job(
                agent=self.selected_agent,
                capabilities=None,  # No capabilities = list request
                config=None
            )
            
            if 'capabilities' in result:
                # Create a properly formatted table for capabilities
                capabilities_table = Table(
                    show_header=True,
                    header_style=f"bold {self.colors['primary']}",
                    border_style=self.colors['dim'],
                    box=MINIMAL,
                    show_lines=False,
                    padding=(0, 2),
                    pad_edge=False
                )
                
                capabilities_table.add_column("CAPABILITY", style=f"bold {self.colors['success']}", min_width=25, no_wrap=True)
                capabilities_table.add_column("DESCRIPTION", style="white", no_wrap=False)
                
                # Add capability rows
                for cap in result['capabilities']:
                    name = cap.get('name', 'unknown')
                    full_desc = cap.get('description', '') or 'No description available'
                    
                    # Cap description length unless --details flag is used
                    if show_details:
                        desc = full_desc
                    else:
                        desc = full_desc[:80] + '...' if len(full_desc) > 80 else full_desc
                    
                    capabilities_table.add_row(name, desc)
                
                self.console.print()
                title = "  Available Capabilities"
                if show_details:
                    title += " (Detailed)"
                else:
                    title += " (use --details for full descriptions)"
                self.console.print(title)
                self.console.print()
                self.console.print(capabilities_table)
            else:
                self.console.print(f"[yellow]  No capabilities available for this agent[/yellow]")
            
            self.console.print()
            self.pause()
        except Exception as e:
            self.console.print(f"[red]Error listing capabilities: {e}[/red]")
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
