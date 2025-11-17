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
from typing import List, Optional
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.model.aegis import Agent

from .utils import (
    relative_time, format_os_display,
    compute_agent_groups, get_agent_display_style
)

# Command handlers
from .commands.set import handle_set as cmd_handle_set
from .commands.help import handle_help as cmd_handle_help
from .commands.list import handle_list as cmd_handle_list
from .commands.ssh import handle_ssh as cmd_handle_ssh
from .commands.info import handle_info as cmd_handle_info
from .commands.job import handle_job as cmd_handle_job

# Command completers
from .commands.set import complete as comp_set
from .commands.help import complete as comp_help
from .commands.list import complete as comp_list
from .commands.ssh import complete as comp_ssh
from .commands.job import complete as comp_job
from .constants import DEFAULT_COLORS


class AegisMenu:
    """Aegis menu interface with modern command-driven UX"""
    
    def __init__(self, sdk: Chariot):
        self.sdk: Chariot = sdk
        self.console = Console()
        self.verbose = VERBOSE
        self.agents: List[Agent] = []
        self.selected_agent: Optional[Agent] = None  
        self._first_render = True
        self.agent_computed_data = {}  
        self.current_prompt = "> "
        self.displayed_agents: List[Agent] = []  # Track currently displayed agents 
        
        self.user_email, self.username = self.sdk.get_current_user()
        
        self.colors = DEFAULT_COLORS
        
        self.commands = [
            'set', 'ssh', 'info', 'list', 'job', 'reload', 'clear', 'help', 'quit', 'exit'
        ]

        self._init_autocomplete()
    
    
    def run(self) -> None:
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
            self.reload_agents()
            
        elif command == 'clear':
            self.clear_screen()
            
        elif command == 'set':
            cmd_handle_set(self, cmd_args)
            
        elif command in ['h', 'help']:
            cmd_handle_help(self, cmd_args)
            
        elif command == 'list':
            cmd_handle_list(self, cmd_args)
            
        elif command == 'ssh':
            cmd_handle_ssh(self, cmd_args)
            
        elif command == 'info':
            cmd_handle_info(self, cmd_args)
            
        elif command == 'job':
            cmd_handle_job(self, cmd_args)
                
        else:
            self.console.print(f"\n  Unknown command: {command}")
            self.console.print(f"  [{self.colors['dim']}]Type 'help' for available commands[/{self.colors['dim']}]\n")
            self.pause()
        
        return True
    
    def clear_screen(self) -> None:
        """Clear the screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def reload_agents(self) -> None:
        """Load agents with 60-second caching and compute status properties"""
        self.load_agents()
        
        if self.verbose and self.agents:
            self.console.print(f"[green]Loaded {len(self.agents)} agents successfully[/green]")
        
    
    def _compute_agent_status(self) -> None:
        """Compute agent status data and groupings using utility function"""
        current_time = datetime.now().timestamp()
        self.agent_computed_data = compute_agent_groups(self.agents, current_time)
    
    def show_agents_list(self, show_offline: bool = False) -> None:
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
        
        self.displayed_agents = [agent for _, agent in display_agents]
        
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
            hostname = agent.hostname
            os_info = agent.os
            os_version = agent.os_version
            os_display = format_os_display(os_info, os_version)
            
            if agent.is_online and agent.has_tunnel:
                group = 'active_tunnel'
            elif agent.is_online:
                group = 'online'
            else:
                group = 'offline'
            
            styles = get_agent_display_style(group, self.colors)
            status = styles['status']
            tunnel = styles['tunnel']
            idx_style = styles['idx_style']
            hostname_style = styles['hostname_style']
            
            current_time = datetime.now().timestamp()
            if agent.last_seen_at and agent.is_online:
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

    def show_main_menu(self) -> None:
        """Show the main interface with reduced noise"""
        if self._first_render:
            current_account = self.sdk.keychain.account
            
            self.console.print(f"\n[bold {self.colors['primary']}]Aegis Agent Interface[/bold {self.colors['primary']}]")
            self.console.print(f"  [{self.colors['dim']}]User: {self.username} | Account: {current_account}[/{self.colors['dim']}]")
            self.console.print(f"  [{self.colors['dim']}]hint: type 'help' for commands[/{self.colors['dim']}]\n")
            
        self._first_render = False
    
    def get_input(self) -> str:
        """Get user input with minimal context-aware prompt"""
        try:
            if self.selected_agent:
                hostname = self.selected_agent.hostname
                self.current_prompt = f"{hostname}> "
            else:
                self.current_prompt = "> "
            
            user_input = input(self.current_prompt).strip()
            return user_input
        except (EOFError, KeyboardInterrupt):
            return "quit"

    def _init_autocomplete(self) -> None:
        """Attach a minimal Tab-completion using readline when available."""
        try:
            import readline  # type: ignore
        except Exception:
            self._readline = None
            return

        self._readline = readline

        try:
            delims = readline.get_completer_delims()
            for ch in "-/.":
                delims = delims.replace(ch, "")
            readline.set_completer_delims(delims)
        except Exception:
            pass

        def completer(text: str, state: int):
            try:
                buf = readline.get_line_buffer()
                beg = getattr(readline, 'get_begidx', lambda: len(buf))()
                before = buf[:beg]
                try:
                    tokens = shlex.split(before)
                except Exception:
                    tokens = before.split()

                if not tokens:
                    options = [c for c in self.commands if c.startswith(text)]
                else:
                    cmd = tokens[0]

                    if len(tokens) == 1 and not before.endswith(' '):
                        options = [c for c in self.commands if c.startswith(text)]
                    else:
                        options = self._autocomplete_options_for(cmd, text, tokens)

                options = sorted(set(options))
                return options[state] if state < len(options) else None
            except Exception:
                return None

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

    def _autocomplete_options_for(self, cmd: str, text: str, tokens: list[str]) -> list[str]:
        """Return simple context-aware options for completion."""
        # Top-level fallbacks
        if cmd in ['quit', 'exit', 'clear', 'reload']:
            return []

        if cmd == 'help':
            return comp_help(self, text, tokens)

        if cmd == 'list':
            return comp_list(self, text, tokens)

        if cmd == 'set':
            return comp_set(self, text, tokens)

        if cmd == 'job':
            return comp_job(self, text, tokens)

        if cmd == 'ssh':
            return comp_ssh(self, text, tokens)

        # Default: no suggestions
        return []
    
    def load_agents(self) -> None:
        """Load agents from SDK"""
        try:
            with self.console.status(
                f"[{self.colors['dim']}]Loading agents...[/{self.colors['dim']}]",
                spinner="dots",
                spinner_style=f"{self.colors['primary']}"
            ):
                agents, _ = self.sdk.aegis.list()
                self.agents = agents or []
                
            if self.verbose or not self.agents:
                agent_count = len(self.agents)
                if agent_count > 0:
                    self.console.print(f"[green]✓ Loaded {agent_count} agents[/green]")
                else:
                    self.console.print(f"[yellow]⚠ No agents found[/yellow]")
                    
        except Exception as e:
            self.console.print(f"[red]✗ Error loading agents: {e}[/red]")
            self.agents = []
    
    def pause(self):
        """Professional pause with styling"""
        if self.verbose:
            Prompt.ask(f"\n[{self.colors['dim']}]Press Enter to continue...[/{self.colors['dim']}]")
        # Quiet mode: do not block


def run_aegis_menu(sdk: Chariot) -> None:
    """Run the Aegis menu interface"""
    menu = AegisMenu(sdk)
    menu.run()