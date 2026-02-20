#!/usr/bin/env python3
"""
Aegis Menu Interface - Clean operator interface
Command-driven approach with intuitive UX
"""

import logging
import os
import shlex
import subprocess
import threading
import time

# Verbosity setting for Aegis UI (quiet by default)
VERBOSE = os.getenv('CHARIOT_AEGIS_VERBOSE') == '1'

from datetime import datetime
from typing import List, Optional
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter, PathCompleter
from prompt_toolkit.history import InMemoryHistory

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.model.aegis import Agent

from .theme import AEGIS_RICH_THEME
from .utils import (
    relative_time, format_os_display,
    compute_agent_groups, get_agent_display_style
)

# Command handlers
from .commands.set import handle_set as cmd_handle_set
from .commands.help import handle_help as cmd_handle_help
from .commands.list import handle_list as cmd_handle_list
from .commands.ssh import handle_ssh as cmd_handle_ssh
from .commands.cp import handle_cp as cmd_handle_cp
from .commands.info import handle_info as cmd_handle_info
from .commands.job import handle_job as cmd_handle_job
from .commands.schedule import handle_schedule as cmd_handle_schedule
from .commands.proxy import handle_proxy as cmd_handle_proxy, stop_all_proxies

from .commands.schedule_helpers import get_cached_schedules
from .constants import DEFAULT_COLORS


class MenuCompleter(Completer):
    """Completer for the main menu with command and argument completion."""

    # Cache TTL for remote directory listings (seconds)
    _REMOTE_LS_TTL = 30

    def __init__(self, menu):
        self.menu = menu

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()

        # Determine what we're completing
        if not words or (len(words) == 1 and not text.endswith(' ')):
            # Completing first word (command)
            prefix = words[0].lower() if words else ''
            for cmd in self.menu.commands:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
        else:
            # Completing arguments
            cmd = words[0].lower()
            # Get the text after the command
            after_cmd = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ''
            current_word = words[-1] if not text.endswith(' ') else ''

            completions = self._get_argument_completions(cmd, after_cmd, current_word, document, complete_event)
            for comp in completions:
                yield comp

    def _get_argument_completions(self, cmd, after_cmd, current_word, document=None, complete_event=None):
        """Get argument completions for a command."""
        words = after_cmd.split()

        if cmd == 'schedule':
            subcommands = ['list', 'view', 'add', 'edit', 'delete', 'pause', 'resume']

            if not words or (len(words) == 1 and not after_cmd.endswith(' ')):
                # Complete subcommand
                prefix = words[0].lower() if words else ''
                for sub in subcommands:
                    if sub.startswith(prefix):
                        yield Completion(sub, start_position=-len(prefix))
            elif len(words) >= 1:
                # Complete schedule ID for commands that need it
                subcmd = words[0].lower()
                if subcmd in ['view', 'edit', 'delete', 'pause', 'resume']:
                    yield from self._get_schedule_completions(current_word)

        elif cmd == 'set':
            # Complete agent numbers/hostnames
            for i, agent in enumerate(self.menu.displayed_agents, 1):
                idx_str = str(i)
                hostname = agent.hostname or ''
                if idx_str.startswith(current_word) or hostname.lower().startswith(current_word.lower()):
                    display = f"{idx_str} - {hostname}"
                    yield Completion(idx_str, start_position=-len(current_word), display=display)

        elif cmd == 'cp':
            # Complete options when current word starts with '-'
            if current_word.startswith('-'):
                cp_opts = ['-u', '-i', '--no-rsync', '--user', '--help']
                for opt in cp_opts:
                    if opt.startswith(current_word):
                        yield Completion(opt, start_position=-len(current_word))
            elif current_word.startswith(':'):
                # Remote file path completion via SSH
                yield from self._get_remote_path_completions(current_word)
            elif document is not None and complete_event is not None:
                # Local file path completion for non-remote tokens
                path_completer = PathCompleter(expanduser=True)
                # Build a sub-document containing just the current word
                from prompt_toolkit.document import Document as PtDocument
                sub_doc = PtDocument(current_word, len(current_word))
                yield from path_completer.get_completions(sub_doc, complete_event)

        elif cmd == 'proxy':
            subcommands = ['list', 'stop', 'help']
            if not words or (len(words) == 1 and not after_cmd.endswith(' ')):
                prefix = words[0].lower() if words else ''
                for sub in subcommands:
                    if sub.startswith(prefix):
                        yield Completion(sub, start_position=-len(prefix))
            elif len(words) >= 1 and words[0].lower() == 'stop':
                # Suggest 'all' and active port numbers
                proxies = getattr(self.menu, '_active_proxies', {})
                options = ['all'] + [str(p) for p in sorted(proxies)]
                for opt in options:
                    if opt.startswith(current_word):
                        yield Completion(opt, start_position=-len(current_word))

        elif cmd == 'job':
            subcommands = ['list', 'run', 'capabilities', 'caps']
            if not words or (len(words) == 1 and not after_cmd.endswith(' ')):
                prefix = words[0].lower() if words else ''
                for sub in subcommands:
                    if sub.startswith(prefix):
                        yield Completion(sub, start_position=-len(prefix))

    def _get_schedule_completions(self, prefix):
        """Get schedule ID completions with metadata (cached to avoid per-keystroke API calls)."""
        try:
            schedules = get_cached_schedules(self.menu)
            if not schedules:
                return

            agent_lookup = getattr(self.menu, 'agent_lookup', {})

            for schedule in schedules:
                schedule_id = schedule.get('scheduleId', '')
                capability = schedule.get('capabilityName', 'unknown')
                status = schedule.get('status', '')
                client_id = schedule.get('clientId', '')
                agent_name = agent_lookup.get(client_id, '') if client_id else ''

                short_id = schedule_id[:10] if schedule_id else ''

                # Match against ID, capability, or agent
                searchable = f"{short_id} {capability} {agent_name}".lower()
                if not prefix or prefix.lower() in searchable:
                    location = agent_name or 'N/A'
                    display_meta = f"{capability[:20]} [{status}] {location}"
                    yield Completion(
                        schedule_id,
                        start_position=-len(prefix),
                        display=short_id,
                        display_meta=display_meta
                    )
        except Exception:
            pass

    def _get_remote_path_completions(self, current_word):
        """Complete remote paths (prefixed with ':') by listing files on the agent via SSH."""
        agent = self.menu.selected_agent
        if not agent or not getattr(agent, 'has_tunnel', False):
            return

        # Strip the ':' prefix to get the raw remote path
        raw_path = current_word[1:]  # e.g. ":/tmp/fo" -> "/tmp/fo"

        # Split into directory and filename prefix
        if '/' in raw_path:
            directory = raw_path.rsplit('/', 1)[0] or '/'
            prefix = raw_path.rsplit('/', 1)[1]
        else:
            # No slash yet — e.g. ":~" or ":foo" — list home directory
            directory = '~'
            prefix = raw_path

        entries = self._list_remote_files(agent, directory)
        if entries is None:
            return

        # Pre-fetch visible subdirectories so drilling deeper is instant
        try:
            client_id = getattr(agent, 'client_id', '') or ''
            public_hostname = agent.health_check.cloudflared_status.hostname
            for entry in entries:
                if entry.endswith('/'):
                    dir_name = entry.rstrip('/')
                    if dir_name.startswith(prefix):
                        if directory == '~' and '/' not in raw_path:
                            sub_dir = f'~/{dir_name}'
                        elif directory == '/':
                            sub_dir = f'/{dir_name}'
                        else:
                            sub_dir = f'{directory}/{dir_name}'
                        sub_key = (client_id, sub_dir)
                        _remote_ls_lookup_or_fetch(self.menu, sub_key, public_hostname, sub_dir)
        except Exception:
            pass

        for entry in entries:
            name = entry.rstrip('/')
            is_dir = entry.endswith('/')
            if name.startswith(prefix):
                # Build the full completion text including the ':' prefix
                if directory == '~' and '/' not in raw_path:
                    completion_text = ':' + name + ('/' if is_dir else '')
                elif directory == '/':
                    completion_text = ':/' + name + ('/' if is_dir else '')
                else:
                    completion_text = ':' + directory + '/' + name + ('/' if is_dir else '')
                yield Completion(
                    completion_text,
                    start_position=-len(current_word),
                    display=entry,
                    display_meta='dir' if is_dir else '',
                )

    def _list_remote_files(self, agent, directory):
        """Return cached remote directory listing, or kick off a background fetch.

        Cache and pending state live on self.menu (AegisMenu) so they
        persist across prompt invocations.
        """
        try:
            cf_status = agent.health_check.cloudflared_status
            public_hostname = cf_status.hostname
            if not public_hostname:
                return None
        except Exception:
            return None

        client_id = getattr(agent, 'client_id', '') or ''
        cache_key = (client_id, directory)

        return _remote_ls_lookup_or_fetch(
            self.menu, cache_key, public_hostname, directory,
        )


# ---------------------------------------------------------------------------
# Remote file-listing helpers (shared between MenuCompleter and AegisMenu)
# ---------------------------------------------------------------------------

_REMOTE_LS_TTL = 30  # seconds


def _remote_ls_lookup_or_fetch(menu, cache_key, public_hostname, directory):
    """Return cached listing or kick off a background SSH fetch.

    Returns list of entries when cached, None otherwise (non-blocking).
    """
    lock = getattr(menu, '_remote_ls_lock', None)
    now = time.monotonic()

    if lock:
        lock.acquire()
    try:
        if cache_key in menu._remote_ls_cache:
            ts, entries = menu._remote_ls_cache[cache_key]
            if now - ts < _REMOTE_LS_TTL:
                return entries

        if cache_key in menu._remote_ls_pending:
            return None

        menu._remote_ls_pending.add(cache_key)
    finally:
        if lock:
            lock.release()

    try:
        _, user = menu.sdk.aegis.api.get_current_user()
    except Exception:
        if lock:
            with lock:
                menu._remote_ls_pending.discard(cache_key)
        else:
            menu._remote_ls_pending.discard(cache_key)
        return None

    thread = threading.Thread(
        target=_fetch_remote_files,
        args=(menu, cache_key, user, public_hostname, directory),
        daemon=True,
    )
    thread.start()
    return None


_logger = logging.getLogger(__name__)


def _fetch_remote_files(menu, cache_key, user, public_hostname, directory):
    """Background worker: SSH into the agent and cache the directory listing."""
    lock = getattr(menu, '_remote_ls_lock', None)
    try:
        ssh_cmd = [
            'ssh', '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'BatchMode=yes',
            f'{user}@{public_hostname}',
            'ls', '-1F', '--', directory,
        ]
        result = subprocess.run(
            ssh_cmd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            entries = [line for line in result.stdout.splitlines() if line]
            if lock:
                with lock:
                    menu._remote_ls_cache[cache_key] = (time.monotonic(), entries)
            else:
                menu._remote_ls_cache[cache_key] = (time.monotonic(), entries)
    except Exception:
        _logger.debug("remote ls failed for %s:%s", public_hostname, directory, exc_info=True)
    finally:
        if lock:
            with lock:
                menu._remote_ls_pending.discard(cache_key)
        else:
            menu._remote_ls_pending.discard(cache_key)


class AegisMenu:
    """Aegis menu interface with modern command-driven UX"""

    def __init__(self, sdk: Chariot):
        self.sdk: Chariot = sdk
        self.console = Console(theme=AEGIS_RICH_THEME)
        self.verbose = VERBOSE
        self.agents: List[Agent] = []
        self.selected_agent: Optional[Agent] = None
        self._first_render = True
        self.agent_computed_data = {}
        self.current_prompt = "> "
        self.displayed_agents: List[Agent] = []  # Track currently displayed agents
        self.agent_lookup: dict[str, str] = {}  # client_id -> hostname mapping for fast lookups
        self._schedule_cache: dict = {'ts': 0, 'items': []}  # Cached schedules with TTL
        # Remote file listing cache (persists across prompts)
        self._remote_ls_cache: dict = {}   # (client_id, dir) -> (timestamp, [entries])
        self._remote_ls_pending: set = set()  # in-flight fetches
        self._remote_ls_lock: threading.Lock = threading.Lock()  # guards cache + pending
        # Command history (up/down arrow)
        self._history = InMemoryHistory()

        self.user_email, self.username = self.sdk.get_current_user()
        
        self.colors = DEFAULT_COLORS
        
        self._active_proxies: dict = {}

        self.commands = [
            'set', 'ssh', 'cp', 'proxy', 'info', 'list', 'job', 'schedule', 'reload', 'clear', 'help', 'quit', 'exit'
        ]

    def prefetch_agent_home(self, agent=None):
        """Pre-fetch common directory listings for the selected agent.

        Called automatically when an agent is selected via ``set`` so that
        ``cp :`` completions are instant.  Pre-fetches both ``~`` and
        ``/tmp`` since they are the most common transfer targets.
        """
        agent = agent or self.selected_agent
        if not agent or not getattr(agent, 'has_tunnel', False):
            return
        try:
            public_hostname = agent.health_check.cloudflared_status.hostname
            if not public_hostname:
                return
        except Exception:
            return
        client_id = getattr(agent, 'client_id', '') or ''
        for directory in ('~', '/tmp'):
            _remote_ls_lookup_or_fetch(
                self, (client_id, directory), public_hostname, directory,
            )

    def run(self) -> None:
        """Main interface loop"""
        self.clear_screen()
        self.reload_agents()

        if self.agents:
            self.show_agents_list()

        try:
            while True:
                try:
                    self.show_main_menu()
                    choice = self.get_input()

                    if not self.handle_choice(choice):
                        break

                except KeyboardInterrupt:
                    # Ctrl-C during command execution - cancel and return to prompt
                    self.console.print(f"\n[{self.colors['dim']}]Cancelled[/{self.colors['dim']}]")
                    continue
        finally:
            stop_all_proxies(self)
    
    def handle_choice(self, choice: str) -> bool:
        """Dead simple command dispatch"""
        if not choice:
            return True  # Just refresh
        
        try:
            args = shlex.split(choice)
        except ValueError:
            self.console.print(f"[{self.colors['error']}]Invalid command syntax: {choice}[/{self.colors['error']}]")
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

        elif command == 'cp':
            cmd_handle_cp(self, cmd_args)

        elif command == 'info':
            cmd_handle_info(self, cmd_args)
            
        elif command == 'job':
            cmd_handle_job(self, cmd_args)

        elif command == 'schedule':
            cmd_handle_schedule(self, cmd_args)

        elif command == 'proxy':
            cmd_handle_proxy(self, cmd_args)

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
            self.console.print(f"[{self.colors['success']}]Loaded {len(self.agents)} agents successfully[/{self.colors['success']}]")
        
    
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
        """Get user input with auto-completing fuzzy prompt.

        Returns:
            str: User input (empty string on Ctrl-C to redisplay prompt)
            "quit": If Ctrl-D was pressed (exit program)
        """
        try:
            if self.selected_agent:
                hostname = self.selected_agent.hostname
                self.current_prompt = f"{hostname}> "
            else:
                self.current_prompt = "> "

            # Use prompt_toolkit for auto-completion as you type
            completer = FuzzyCompleter(MenuCompleter(self))
            pending = self._remote_ls_pending  # reference for closure

            def _toolbar():
                if pending:
                    return ' loading remote files…'
                return ''

            user_input = pt_prompt(
                self.current_prompt,
                completer=completer,
                complete_while_typing=True,
                bottom_toolbar=_toolbar,
                history=self._history,
            )
            return user_input.strip()
        except KeyboardInterrupt:
            # Ctrl-C: cancel current input, return to prompt
            self.console.print()
            return ""
        except EOFError:
            # Ctrl-D: exit program
            return "quit"

    def load_agents(self) -> None:
        """Load agents from SDK and build lookup cache"""
        try:
            with self.console.status(
                f"[{self.colors['dim']}]Loading agents...[/{self.colors['dim']}]",
                spinner="dots",
                spinner_style=f"{self.colors['primary']}"
            ):
                agents, _ = self.sdk.aegis.list()
                self.agents = agents or []

                # Build agent_lookup for fast client_id -> hostname mapping
                self.agent_lookup = {}
                for agent in self.agents:
                    if agent.client_id and agent.hostname:
                        self.agent_lookup[agent.client_id] = agent.hostname

            if self.verbose or not self.agents:
                agent_count = len(self.agents)
                if agent_count > 0:
                    self.console.print(f"[{self.colors['success']}]✓ Loaded {agent_count} agents[/{self.colors['success']}]")
                else:
                    self.console.print(f"[{self.colors['warning']}]⚠ No agents found[/{self.colors['warning']}]")

        except Exception as e:
            self.console.print(f"[{self.colors['error']}]✗ Error loading agents: {e}[/{self.colors['error']}]")
            self.agents = []
            self.agent_lookup = {}
    
    def pause(self):
        """Professional pause with styling"""
        if self.verbose:
            Prompt.ask(f"\n[{self.colors['dim']}]Press Enter to continue...[/{self.colors['dim']}]")
        # Quiet mode: do not block


def run_aegis_menu(sdk: Chariot) -> None:
    """Run the Aegis menu interface"""
    menu = AegisMenu(sdk)
    menu.run()