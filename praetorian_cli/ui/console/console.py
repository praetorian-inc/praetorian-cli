#!/usr/bin/env python3
"""Guard Interactive Console — operator-focused engagement interface."""

import json
import os
import shlex
import time
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.ui.aegis.theme import (
    AEGIS_COLORS, AEGIS_RICH_THEME,
    PRIMARY_RED, COMPLEMENTARY_GOLD, SECONDARY_TEXT,
)
from praetorian_cli.ui.console.context import EngagementContext


CONSOLE_COMMANDS = [
    'set', 'unset', 'show', 'switch',
    'use', 'options', 'execute', 'exploit', 'back',
    'accounts', 'engagements', 'home', 'su',
    'search', 'find', 'assets', 'risks', 'jobs', 'info',
    'scan', 'tag',
    'run', 'status', 'download', 'install', 'installed',
    'asset-analyzer', 'brutus', 'julius', 'augustus', 'aurelius',
    'trajan', 'cato', 'priscus', 'seneca', 'titus',
    'nuclei', 'portscan', 'subdomain', 'crawler', 'capabilities',
    'evidence', 'report',
    'ask', 'marcus',
    'aegis',
    'configure', 'login',
    'help', 'history', 'clear', 'quit', 'exit',
]


class GuardConsole:
    """Interactive operator console for Guard engagements."""

    def __init__(self, sdk: Chariot, account: Optional[str] = None):
        self.sdk = sdk
        self.console = Console(theme=AEGIS_RICH_THEME)
        self.colors = AEGIS_COLORS
        self.context = EngagementContext(account=account)

        history_path = os.path.expanduser('~/.praetorian/console_history')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        self.session = PromptSession(
            history=FileHistory(history_path),
            completer=WordCompleter(CONSOLE_COMMANDS, ignore_case=True),
        )

    def run(self):
        """Main console loop."""
        self._show_banner()

        while True:
            try:
                prompt_text = self._build_prompt()
                user_input = self.session.prompt(prompt_text).strip()
                if not user_input:
                    continue
                self._dispatch(user_input)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    def _build_prompt(self):
        """Build a colored prompt — Praetorian red for guard, gold for subshells."""
        if self.context.active_tool:
            tool = self.context.active_tool
            target = self.context.target or ''
            if target:
                # Truncate long target keys for prompt readability
                display_target = target if len(target) <= 40 else target[:37] + '...'
                return HTML(
                    f'<style fg="{PRIMARY_RED}" bg="">guard</style>'
                    f' <style fg="{COMPLEMENTARY_GOLD}" bg="">({tool})</style>'
                    f' <style fg="{SECONDARY_TEXT}">[{display_target}]</style>'
                    f' <style fg="{PRIMARY_RED}" bg="">&gt;</style> '
                )
            return HTML(
                f'<style fg="{PRIMARY_RED}" bg="">guard</style>'
                f' <style fg="{COMPLEMENTARY_GOLD}" bg="">({tool})</style>'
                f' <style fg="{PRIMARY_RED}" bg="">&gt;</style> '
            )
        return HTML(f'<style fg="{PRIMARY_RED}" bg="">guard &gt;</style> ')

    def _show_banner(self):
        banner = Text()
        banner.append('Guard Console', style=f'bold {self.colors["primary"]}')
        banner.append(' — interactive operator interface\n', style=self.colors['dim'])
        banner.append(f'Context: {self.context.summary()}', style=self.colors['dim'])
        self.console.print(Panel(banner, border_style=self.colors['primary']))
        self.console.print(f'[dim]Type "help" for commands.[/dim]\n')

    def _dispatch(self, user_input: str):
        """Route user input to the appropriate command handler."""
        try:
            parts = shlex.split(user_input)
        except ValueError:
            parts = user_input.split()

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        from praetorian_cli.handlers.run import TOOL_ALIASES

        handlers = {
            'set': self._cmd_set,
            'unset': self._cmd_unset,
            'show': self._cmd_show,
            'use': self._cmd_use,
            'options': self._cmd_options,
            'execute': self._cmd_execute,
            'exploit': self._cmd_execute,
            'back': self._cmd_back,
            'search': self._cmd_search,
            'find': self._cmd_find,
            'accounts': self._cmd_accounts,
            'engagements': self._cmd_accounts,
            'switch': self._cmd_switch,
            'home': self._cmd_home,
            'su': self._cmd_home,
            'assets': self._cmd_assets,
            'risks': self._cmd_risks,
            'jobs': self._cmd_jobs,
            'info': self._cmd_info,
            'scan': self._cmd_scan,
            'tag': self._cmd_tag,
            'run': self._cmd_run,
            'status': self._cmd_status,
            'download': self._cmd_download,
            'install': self._cmd_install,
            'installed': self._cmd_installed,
            'capabilities': self._cmd_capabilities,
            'evidence': self._cmd_evidence,
            'report': self._cmd_report,
            'ask': self._cmd_ask,
            'marcus': self._cmd_marcus,
            'aegis': self._cmd_aegis,
            'configure': self._cmd_configure,
            'login': self._cmd_configure,
            'help': self._cmd_help,
            'clear': self._cmd_clear,
            'quit': self._cmd_quit_or_back,
            'exit': self._cmd_quit_or_back,
        }

        # Direct tool name aliases: "brutus <key>" → "run brutus <key>"
        if cmd in TOOL_ALIASES:
            try:
                self._cmd_run([cmd] + args)
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception as e:
                self.console.print(f'[error]Error: {e}[/error]')
            return

        handler = handlers.get(cmd)
        if handler:
            try:
                handler(args)
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception as e:
                self.console.print(f'[error]Error: {e}[/error]')
        elif self.context.active_tool:
            # When a tool is selected, treat unknown input as "set target + execute"
            target_input = user_input.strip()
            try:
                from praetorian_cli.handlers.run import resolve_target
                alias = TOOL_ALIASES[self.context.active_tool]
                resolved, warning = resolve_target(self.sdk, target_input, alias['target_type'])
                if resolved:
                    self.context.target = resolved
                    if warning:
                        self.console.print(f'[warning]{warning}[/warning]')
                    self.console.print(f'[success]TARGET => {resolved}[/success]')
                    self._cmd_execute([])
                else:
                    self.console.print(f'[error]{warning}[/error]')
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception as e:
                self.console.print(f'[error]{e}[/error]')
        else:
            self.console.print(f'[dim]Unknown command: {cmd}. Type "help" for available commands.[/dim]')

    # ── Context commands ─────────────────────────────────────────

    def _cmd_set(self, args):
        if len(args) < 2:
            self.console.print('[dim]Usage: set <account|scope|mode|target> <value>[/dim]')
            return
        key, value = args[0].lower(), ' '.join(args[1:])
        if key == 'account':
            self.context.account = value
            self.context.clear_conversation()
            self.console.print(f'[success]Account set to {value}[/success]')
        elif key == 'scope':
            self.context.scope = value
            self.console.print(f'[success]Scope set to {value}[/success]')
        elif key == 'mode':
            if value in ('query', 'agent'):
                self.context.mode = value
                self.console.print(f'[success]Mode set to {value}[/success]')
            else:
                self.console.print('[error]Mode must be "query" or "agent"[/error]')
        elif key in ('target', 'rhost', 'rhosts'):
            # Resolve numeric refs from show targets / assets / risks listings
            if value.isdigit():
                if hasattr(self, '_target_list') and self._target_list:
                    idx = int(value) - 1
                    if 0 <= idx < len(self._target_list):
                        value = self._target_list[idx]
                    else:
                        self.console.print(f'[error]Invalid number (1-{len(self._target_list)}). Run "show targets" or "assets" first.[/error]')
                        return
                else:
                    self.console.print(f'[dim]No target list loaded. Run "show targets", "assets", or "risks" first.[/dim]')
                    return
            # Resolve friendly names to Guard keys
            if not value.startswith('#') and self.context.active_tool:
                from praetorian_cli.handlers.run import resolve_target, TOOL_ALIASES
                alias = TOOL_ALIASES.get(self.context.active_tool, {})
                resolved, warning = resolve_target(self.sdk, value, alias.get('target_type', 'asset'))
                if resolved:
                    value = resolved
                    if warning:
                        self.console.print(f'[warning]{warning}[/warning]')
                else:
                    self.console.print(f'[error]{warning}[/error]')
                    return
            self.context.target = value
            self.console.print(f'[success]TARGET => {value}[/success]')
        else:
            self.console.print(f'[dim]Unknown setting: {key}. Use: account, scope, mode, target[/dim]')

    def _cmd_unset(self, args):
        if not args:
            self.console.print('[dim]Usage: unset <scope>[/dim]')
            return
        key = args[0].lower()
        if key == 'scope':
            self.context.scope = None
            self.console.print('[success]Scope cleared[/success]')
        else:
            self.console.print(f'[dim]Cannot unset: {key}[/dim]')

    def _cmd_show(self, args):
        from praetorian_cli.handlers.run import TOOL_ALIASES
        target = args[0].lower() if args else 'context'
        if target == 'context':
            table = Table(title='Engagement Context', border_style=self.colors['primary'])
            table.add_column('Setting', style=self.colors['primary'])
            table.add_column('Value')
            table.add_row('Account', self.context.account or '[dim]not set[/dim]')
            table.add_row('Scope', self.context.scope or '[dim]not set[/dim]')
            table.add_row('Mode', self.context.mode)
            table.add_row('Tool', self.context.active_tool or '[dim]none[/dim]')
            table.add_row('Target', self.context.target or '[dim]not set[/dim]')
            table.add_row('Agent', self.context.active_agent or '[dim]default[/dim]')
            table.add_row('Conversation', self.context.conversation_id[:8] + '...' if self.context.conversation_id else '[dim]none[/dim]')
            self.console.print(table)
        elif target in ('targets', 'hosts'):
            self._show_targets()
        elif target in ('options', 'info'):
            self._cmd_options(args[1:])
        elif target == 'tools':
            self._cmd_run([])
        elif target == 'assets':
            self._cmd_assets(args[1:])
        elif target == 'risks':
            self._cmd_risks(args[1:])
        elif target == 'jobs':
            self._cmd_jobs(args[1:])
        elif target in ('accounts', 'engagements'):
            self._cmd_accounts(args[1:])
        elif target.isdigit():
            # "show 1" — show detail of item # from last listing
            self._show_detail_by_number(int(target))
        else:
            self.console.print(f'[dim]Unknown: show {target}. Try: context, targets, assets, risks, jobs, tools, options, or a number.[/dim]')

    def _show_targets(self):
        """Show available targets (assets/seeds/ports) for the active tool."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        alias = TOOL_ALIASES.get(self.context.active_tool) if self.context.active_tool else None
        target_type = alias['target_type'] if alias else 'asset'

        with self.console.status('Fetching targets...', spinner='dots', spinner_style=self.colors['primary']):
            try:
                from praetorian_cli.sdk.model.query import Query, Node
                scope_filter = self.context.scope or ''
                search_val = scope_filter if scope_filter else None

                # Map target type to the right query
                type_to_label = {
                    'port': Node.Label.PORT,
                    'webpage': Node.Label.WEBPAGE,
                    'webapplication': Node.Label.WEBAPPLICATION,
                    'repository': Node.Label.REPOSITORY,
                    'risk': Node.Label.RISK,
                }

                if target_type in type_to_label:
                    label = type_to_label[target_type]
                    q = Query(node=Node(labels=[label], search=search_val), limit=50)
                    results, _ = self.sdk.search.by_query(q, pages=1)
                elif target_type == 'asset':
                    results, _ = self.sdk.assets.list(scope_filter, pages=1)
                else:
                    # Fallback: try graph query with generic search
                    results, _ = self.sdk.assets.list(scope_filter, pages=1)
            except Exception as e:
                self.console.print(f'[error]{e}[/error]')
                return

        if not results:
            self.console.print('[dim]No targets found.[/dim]')
            if self.context.scope:
                self.console.print(f'[dim]Scope: {self.context.scope} — use "unset scope" to broaden[/dim]')
            return

        table = Table(
            title=f'Available Targets ({target_type}) — {len(results)} found',
            border_style=self.colors['primary'],
        )
        table.add_column('#', style=self.colors['dim'], width=4)
        table.add_column('Key', style=self.colors['primary'])
        table.add_column('Name/DNS', style='white')
        table.add_column('Status', style=self.colors['accent'])

        self._target_list = []
        for i, item in enumerate(results[:50], 1):
            key = item.get('key', '')
            name = item.get('name', item.get('dns', item.get('url', item.get('title', ''))))
            status = item.get('status', '')
            table.add_row(str(i), key, str(name), status)
            self._target_list.append(key)

        self.console.print(table)
        self.console.print(f'\n[dim]Use "set target <key>" or "set target <#>" to select a target[/dim]')

    def _show_detail_by_number(self, num: int):
        """Show detail of item # from the last listing (_target_list)."""
        if not hasattr(self, '_target_list') or not self._target_list:
            self.console.print('[dim]No listing loaded. Run "assets", "risks", or "show targets" first.[/dim]')
            return
        idx = num - 1
        if idx < 0 or idx >= len(self._target_list):
            self.console.print(f'[error]Invalid number (1-{len(self._target_list)}).[/error]')
            return
        key = self._target_list[idx]
        try:
            if '#risk#' in key:
                result = self.sdk.risks.get(key, details=True)
                if result:
                    self._render_entity_detail(result, 'Risk')
                else:
                    self.console.print(f'[dim]Not found: {key}[/dim]')
            elif '#asset#' in key or '#webapplication#' in key:
                result = self.sdk.assets.get(key, details=True)
                if result:
                    self._render_entity_detail(result, 'Asset')
                else:
                    self.console.print(f'[dim]Not found: {key}[/dim]')
            else:
                result = self.sdk.search.by_exact_key(key, get_attributes=True)
                if result:
                    self.console.print_json(json.dumps(result, indent=2))
                else:
                    self.console.print(f'[dim]Not found: {key}[/dim]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _render_entity_detail(self, entity: dict, entity_type: str):
        """Render a rich detail view for an asset or risk."""
        key = entity.get('key', '')
        name = entity.get('name', entity.get('dns', ''))
        status = entity.get('status', '')
        created = entity.get('created', '')

        # Header
        header = Text()
        header.append(f'{name}\n', style=f'bold {self.colors["primary"]}')
        header.append(f'Key: {key}\n', style=self.colors['dim'])
        header.append(f'Status: ', style=self.colors['dim'])
        header.append(f'{status}', style=f'bold {self.colors["accent"]}')
        if created:
            header.append(f'  Created: {created}', style=self.colors['dim'])

        if entity_type == 'Risk':
            priority = entity.get('priority', '')
            severity_map = {0: 'CRITICAL', 10: 'HIGH', 20: 'MEDIUM', 30: 'LOW', 40: 'INFO', 60: 'EXPOSURE'}
            severity = severity_map.get(priority, str(priority))
            header.append(f'\nSeverity: ', style=self.colors['dim'])
            header.append(f'{severity}', style=f'bold {self.colors["error"]}' if priority <= 10 else f'{self.colors["accent"]}')
            title = entity.get('title', '')
            if title:
                header.append(f'\nTitle: {title}', style='white')

        if entity_type == 'Asset':
            cls = entity.get('class', '')
            dns = entity.get('dns', '')
            surface = entity.get('attackSurface', [])
            if cls:
                header.append(f'\nClass: {cls}', style=self.colors['dim'])
            if dns and dns != name:
                header.append(f'  DNS: {dns}', style=self.colors['dim'])
            if surface:
                header.append(f'  Surface: {", ".join(surface)}', style=self.colors['dim'])

        self.console.print(Panel(header, title=entity_type, border_style=self.colors['primary']))

        # Attributes
        attrs = entity.get('attributes', [])
        if attrs:
            table = Table(title=f'Attributes ({len(attrs)})', border_style=self.colors['dim'])
            table.add_column('Name', style=self.colors['primary'])
            table.add_column('Value', style='white')
            for a in attrs[:20]:
                table.add_row(a.get('name', ''), str(a.get('value', '')))
            self.console.print(table)

        # Associated risks (for assets)
        assoc_risks = entity.get('associated_risks', [])
        if assoc_risks:
            table = Table(title=f'Associated Risks ({len(assoc_risks)})', border_style=self.colors['error'])
            table.add_column('Risk', style=self.colors['primary'])
            table.add_column('Status', style=self.colors['accent'])
            for r in assoc_risks[:10]:
                table.add_row(r.get('name', r.get('key', '')), r.get('status', ''))
            self.console.print(table)

        # Affected assets (for risks)
        affected = entity.get('affected_assets', [])
        if affected:
            table = Table(title=f'Affected Assets ({len(affected)})', border_style=self.colors['primary'])
            table.add_column('Asset', style=self.colors['primary'])
            table.add_column('Status', style=self.colors['accent'])
            for a in affected[:10]:
                table.add_row(a.get('key', ''), a.get('status', ''))
            self.console.print(table)

        # History (for risks)
        history = entity.get('history', [])
        if history:
            table = Table(title='History', border_style=self.colors['dim'])
            table.add_column('Date', style=self.colors['dim'])
            table.add_column('By', style='white')
            table.add_column('Change', style=self.colors['accent'])
            for h in history[:10]:
                table.add_row(
                    h.get('updated', ''),
                    h.get('by', ''),
                    f'{h.get("from", "")} → {h.get("to", "")}',
                )
            self.console.print(table)

    def _cmd_use(self, args):
        """Select a tool or switch engagement — context-aware."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        if not args:
            self._cmd_run([])  # show available tools
            return

        name = args[0]

        # If it's a number, switch engagement (or hint to run accounts first)
        if name.isdigit():
            if hasattr(self, '_account_list') and self._account_list:
                self._cmd_switch([name])
            else:
                self.console.print(f'[dim]Run "accounts" first to load the engagement list, then "use <#>".[/dim]')
            return

        # If it looks like an email, switch engagement
        if '@' in name:
            self._cmd_switch([name])
            return

        # Otherwise, select a tool
        tool_name = name.lower()
        if tool_name not in TOOL_ALIASES:
            available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
            self.console.print(f'[error]Unknown tool: {tool_name}. Available: {available}[/error]')
            return
        alias = TOOL_ALIASES[tool_name]
        self.context.active_tool = tool_name
        self.context.active_tool_config = dict(alias.get('default_config', {}))
        self.console.print(f'[info]Using {tool_name} — {alias["description"]}[/info]')
        self.console.print(f'[dim]Target type: {alias["target_type"]}. Use "show targets" to see valid targets.[/dim]')

    def _cmd_options(self, args):
        """Show current tool options — Metasploit-style."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        if not self.context.active_tool:
            self.console.print('[dim]No tool selected. Use "use <tool>" first.[/dim]')
            return
        alias = TOOL_ALIASES[self.context.active_tool]
        table = Table(title=f'Options: {self.context.active_tool}', border_style=self.colors['primary'])
        table.add_column('Name', style=f'bold {self.colors["primary"]}', min_width=15)
        table.add_column('Current Value', min_width=20)
        table.add_column('Required', style=self.colors['accent'])
        table.add_column('Description')
        table.add_row('TARGET', self.context.target or '', 'yes', f'Target {alias["target_type"]} key')
        config = self.context.active_tool_config or {}
        for k, v in config.items():
            table.add_row(k, str(v), 'no', f'Config: {k}')
        if alias.get('agent'):
            table.add_row('USE_AGENT', 'false', 'no', f'Route through {alias["agent"]} for AI analysis')
        self.console.print(table)

    def _cmd_execute(self, args):
        """Execute the active tool against the target — Metasploit-style."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        if not self.context.active_tool:
            self.console.print('[error]No tool selected. Use "use <tool>" first.[/error]')
            return
        target = self.context.target
        if not target:
            self.console.print('[error]No target set. Use "set target <key>" or "show targets".[/error]')
            return
        # Allow numeric target from show targets list
        if target.isdigit() and hasattr(self, '_target_list'):
            idx = int(target) - 1
            if 0 <= idx < len(self._target_list):
                target = self._target_list[idx]
                self.context.target = target
            else:
                self.console.print(f'[error]Invalid target number. Use "show targets".[/error]')
                return

        self._cmd_run([self.context.active_tool, target] + (['--wait'] if '--wait' in args else []))

    def _cmd_back(self, args):
        """Clear tool selection — Metasploit-style."""
        if self.context.active_tool:
            self.console.print(f'[dim]Deselected {self.context.active_tool}[/dim]')
            self.context.clear_tool()
        else:
            self.console.print('[dim]Nothing to go back from.[/dim]')

    # ── Account / Engagement commands ────────────────────────────

    def _cmd_accounts(self, args):
        """List accounts/engagements, or 'use' one to switch context."""
        # Handle subcommands: engagements use <#>, engagements create, engagements vault
        if args:
            subcmd = args[0].lower()
            if subcmd == 'use' and len(args) > 1:
                self._cmd_switch(args[1:])
                return
            if subcmd == 'create':
                self._engagement_create(args[1:])
                return
            if subcmd == 'vault':
                self._engagement_vault(args[1:])
                return
            if subcmd == 'onboard':
                self._engagement_onboard(args[1:])
                return
        try:
            with self.console.status('Fetching accounts...', spinner='dots', spinner_style=self.colors['primary']):
                accounts_list, _ = self.sdk.accounts.list()

            if not accounts_list:
                self.console.print('[dim]No accounts found.[/dim]')
                return

            # Separate into: accounts I own (collaborators on my account) vs accounts I can access
            current = self.sdk.accounts.current_principal()
            login = self.sdk.accounts.login_principal()

            authorized = []
            collaborators = []
            for acct in accounts_list:
                if acct.get('member') == (login or current):
                    # I'm listed as member → this is an account I can access
                    authorized.append(acct)
                elif acct.get('name') == (login or current):
                    # I own this account → this person collaborates with me
                    collaborators.append(acct)
                else:
                    authorized.append(acct)

            self._account_list = []

            if authorized:
                table = Table(
                    title=f'Engagements / Authorized Accounts ({len(authorized)})',
                    border_style=self.colors['primary'],
                )
                table.add_column('#', style=self.colors['dim'], width=4)
                table.add_column('Account', style=f'bold {self.colors["primary"]}')
                table.add_column('Role', style=self.colors['accent'])
                table.add_column('Active', style=self.colors['success'])

                for i, acct in enumerate(authorized, 1):
                    account_email = acct.get('name', '')
                    role = acct.get('role', acct.get('value', ''))
                    is_active = '→' if account_email == self.context.account else ''
                    table.add_row(str(i), account_email, role, is_active)
                    self._account_list.append(account_email)

                self.console.print(table)

            if collaborators:
                table = Table(
                    title=f'Collaborators on Your Account ({len(collaborators)})',
                    border_style=self.colors['dim'],
                )
                table.add_column('Email', style='white')
                table.add_column('Role', style=self.colors['accent'])
                for acct in collaborators:
                    table.add_row(acct.get('member', ''), acct.get('role', acct.get('value', '')))
                self.console.print(table)

            self.console.print(f'\n[dim]Use "engagements use <#>" or "switch <email>" to change engagement[/dim]')
            self.console.print(f'[dim]Use "engagements create" to onboard a new customer[/dim]')

        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_switch(self, args):
        """Switch to a different account/engagement."""
        if not args:
            self.console.print('[dim]Usage: switch <account_email or #>[/dim]')
            self.console.print('[dim]Run "accounts" first to see available accounts.[/dim]')
            return

        target = args[0]

        # Allow numeric selection from accounts list
        if target.isdigit() and hasattr(self, '_account_list'):
            idx = int(target) - 1
            if 0 <= idx < len(self._account_list):
                target = self._account_list[idx]
            else:
                self.console.print(f'[error]Invalid number. Run "accounts" to see the list.[/error]')
                return

        self.context.account = target
        self.context.clear_conversation()
        self.context.clear_tool()
        # Update SDK impersonation so all API calls use this account
        self.sdk.keychain.account = target
        # Clear stale target/account lists from previous engagement
        self._target_list = []
        self.console.print(f'[success]Switched to {target}[/success]')
        self._show_engagement_status()

    def _cmd_home(self, args):
        """Return to your own account — unimpersonate."""
        self.context.account = None
        self.context.clear_conversation()
        self.context.clear_tool()
        self.sdk.keychain.account = None
        self._target_list = []
        login = self.sdk.accounts.login_principal() or 'your account'
        self.console.print(f'[success]Returned to {login}[/success]')

    def _show_engagement_status(self):
        """Show a summary panel for the active engagement after switching."""
        if not self.context.account:
            return
        try:
            with self.console.status('Loading engagement...', spinner='dots', spinner_style=self.colors['primary']):
                stats = {}
                try:
                    seeds, _ = self.sdk.search.by_key_prefix('#seed#', pages=1)
                    stats['seeds'] = len(seeds) if seeds else 0
                except Exception:
                    stats['seeds'] = '?'
                try:
                    assets, _ = self.sdk.assets.list('', pages=1)
                    stats['assets'] = len(assets) if assets else 0
                except Exception:
                    stats['assets'] = '?'
                try:
                    risks, _ = self.sdk.risks.list('', pages=1)
                    stats['risks'] = len(risks) if risks else 0
                except Exception:
                    stats['risks'] = '?'

            status_text = Text()
            status_text.append(f'{self.context.account}\n', style=f'bold {self.colors["primary"]}')
            status_text.append(f'Seeds: ', style=self.colors['dim'])
            status_text.append(f'{stats["seeds"]}', style='bold white')
            status_text.append(f'  Assets: ', style=self.colors['dim'])
            status_text.append(f'{stats["assets"]}', style='bold white')
            status_text.append(f'  Risks: ', style=self.colors['dim'])
            status_text.append(f'{stats["risks"]}', style='bold white')
            self.console.print(Panel(status_text, title='Engagement', border_style=self.colors['accent']))
        except Exception:
            pass  # Don't block on status fetch failure

    def _engagement_create(self, args):
        """Create a new customer — console wrapper."""
        # Parse simple key=value args
        params = {}
        for a in args:
            if '=' in a:
                k, v = a.split('=', 1)
                params[k] = v

        email = params.get('email', '')
        name = params.get('name', '')

        if not email or not name:
            self.console.print('[dim]Usage: engagements create email=ops@acme.com name="ACME Corp"[/dim]')
            self.console.print('[dim]Optional: type=ENGAGEMENT scan-level=A[/dim]')
            return

        from praetorian_cli.handlers.engagement import _generate_password
        body = {
            'username': email,
            'password': _generate_password(),
            'settings_display_name': name,
            'scan_level': params.get('scan-level', 'A'),
            'customer_type': params.get('type', 'ENGAGEMENT'),
        }

        try:
            with self.console.status('Creating customer...', spinner='dots', spinner_style=self.colors['primary']):
                result = self.sdk.post('customer/onboard', body)
            self.console.print(f'[success]Customer created: {email} ({name})[/success]')
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _engagement_vault(self, args):
        """Create engagement vault — routes through Marcus."""
        params = {}
        for a in args:
            if '=' in a:
                k, v = a.split('=', 1)
                params[k] = v

        client = params.get('client', '')
        sow = params.get('sow', '')
        sku = params.get('sku', '')
        github_user = params.get('github-user', '')

        if not client or not sow or not sku or not github_user:
            self.console.print('[dim]Usage: engagements vault client=acme sow=SOW-1234 sku=WAPT github-user=jdoe[/dim]')
            return

        message = (
            f'Create a vault repository for client "{client}" with SOW number "{sow}". '
            f'SKUs: {sku}. Add GitHub user "{github_user}" as admin. '
            f'Use the github_vault tool.'
        )
        self.console.print(f'[info]Creating vault for {client}...[/info]')
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Vault Created', border_style=self.colors['accent']))

    def _engagement_onboard(self, args):
        """Full onboarding — routes through Marcus."""
        params = {}
        seeds = []
        for a in args:
            if '=' in a:
                k, v = a.split('=', 1)
                if k == 'seed':
                    seeds.append(v)
                else:
                    params[k] = v

        email = params.get('email', '')
        name = params.get('name', '')

        if not email or not name:
            self.console.print('[dim]Usage: engagements onboard email=ops@acme.com name="ACME Corp" seed=acme.com seed=10.0.0.0/24[/dim]')
            return

        message = (
            f'Onboard a new engagement for {name} (email: {email}). '
            f'Create the customer account using customer_create. '
        )
        if seeds:
            message += f'Add these seeds: {", ".join(seeds)}. '
        sow = params.get('sow', '')
        if sow:
            message += f'Read the SOW at "{sow}" for additional scope. '
        message += 'Report what you created.'

        self.console.print(f'[info]Onboarding {name}...[/info]')
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Onboarding Complete', border_style=self.colors['accent']))

    # ── Search commands ──────────────────────────────────────────

    def _cmd_search(self, args):
        if not args:
            self.console.print('[dim]Usage: search <term> [--kind <type>][/dim]')
            return
        term = ' '.join(args)
        try:
            kind = None
            if '--kind' in args:
                idx = args.index('--kind')
                if idx + 1 < len(args):
                    kind = args[idx + 1]
                    term = ' '.join(args[:idx])

            results, offset = self.sdk.search.by_term(term, kind)
            self._render_results(results, f'Search: {term}')
        except Exception as e:
            self.console.print(f'[error]Search failed: {e}[/error]')

    def _cmd_find(self, args):
        if not args:
            self.console.print('[dim]Usage: find <term> [--type <type>] [--limit <n>][/dim]')
            return
        from praetorian_cli.sdk.model.query import Query, Node, KIND_TO_LABEL

        # Parse args
        term = []
        kind = None
        limit = 100
        i = 0
        while i < len(args):
            if args[i] == '--type' and i + 1 < len(args):
                kind = args[i + 1]
                i += 2
            elif args[i] == '--limit' and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            else:
                term.append(args[i])
                i += 1
        term = ' '.join(term)

        if kind:
            label = KIND_TO_LABEL.get(kind)
            if not label:
                self.console.print(f'[error]Unknown type: {kind}[/error]')
                return
            queries = [Query(node=Node(labels=[label], search=term), limit=limit)]
        else:
            queries = [
                Query(node=Node(labels=[Node.Label.ASSET], search=term), limit=limit),
                Query(node=Node(labels=[Node.Label.RISK], search=term), limit=limit),
                Query(node=Node(labels=[Node.Label.ATTRIBUTE], search=term), limit=limit),
                Query(node=Node(labels=[Node.Label.WEBPAGE], search=term), limit=limit),
            ]

        all_results = []
        for q in queries:
            try:
                results, _ = self.sdk.search.by_query(q, pages=1)
                all_results.extend(results)
            except Exception:
                pass

        self._render_results(all_results, f'Find: {term}')
        if len(all_results) >= limit:
            self.console.print(f'[warning]Showing {limit} results. Use --limit to increase.[/warning]')

    def _cmd_assets(self, args):
        try:
            filter_text = self.context.scope or ''
            results, _ = self.sdk.assets.list(filter_text, pages=1)
            self._render_results(results, 'Assets')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_risks(self, args):
        try:
            filter_text = self.context.scope or ''
            results, _ = self.sdk.risks.list(filter_text, pages=1)
            self._render_results(results, 'Risks')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_jobs(self, args):
        """List jobs, optionally filtered. Also supports 'jobs <key>' to check a specific job."""
        filter_term = ' '.join(args) if args else ''
        try:
            results, _ = self.sdk.jobs.list(filter_term, pages=1)
            if not results:
                self.console.print('[dim]No jobs found.[/dim]')
                return

            table = Table(title=f'Jobs ({len(results)} results)', border_style=self.colors['primary'])
            table.add_column('#', style=self.colors['dim'], width=4)
            table.add_column('Capability', style=f'bold {self.colors["primary"]}')
            table.add_column('Target', style='white')
            table.add_column('Status', min_width=8)
            table.add_column('Created', style=self.colors['dim'])

            for i, job in enumerate(results[:50], 1):
                key = job.get('key', '')
                source = job.get('source', '')
                cap = source.split('#')[0] if '#' in source else source
                dns = job.get('dns', '')
                status_raw = job.get('status', '')
                status_code = status_raw[:2] if status_raw else '?'
                created = job.get('created', '')[:16]

                # Color status
                status_map = {
                    'JQ': (f'[info]QUEUED[/info]'),
                    'JR': (f'[accent]RUNNING[/accent]'),
                    'JP': (f'[success]PASSED[/success]'),
                    'JF': (f'[error]FAILED[/error]'),
                }
                status_display = status_map.get(status_code, status_code)
                table.add_row(str(i), cap, dns, status_display, created)

            self.console.print(table)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_status(self, args):
        """Check status of last job or a specific job key."""
        job_key = ''
        if args:
            job_key = args[0]
        elif hasattr(self.context, '_last_job_key') and self.context._last_job_key:
            job_key = self.context._last_job_key
        else:
            self.console.print('[dim]No recent job. Usage: status <job_key>[/dim]')
            self.console.print('[dim]Or run a tool first, then "status" to check it.[/dim]')
            return

        try:
            job = self.sdk.jobs.get(job_key)
            if not job:
                self.console.print(f'[dim]Job not found: {job_key}[/dim]')
                return

            status_raw = job.get('status', '')
            status_code = status_raw[:2]
            status_map = {
                'JQ': ('QUEUED', self.colors['info']),
                'JR': ('RUNNING', self.colors['accent']),
                'JP': ('PASSED', self.colors['success']),
                'JF': ('FAILED', self.colors['error']),
            }
            status_label, color = status_map.get(status_code, (status_code, self.colors['dim']))

            source = job.get('source', '')
            cap = source.split('#')[0] if '#' in source else source
            dns = job.get('dns', '')
            created = job.get('created', '')
            started = job.get('started', '') or '—'
            finished = job.get('finished', '') or '—'

            status_text = Text()
            status_text.append(f'{cap}', style=f'bold {self.colors["primary"]}')
            status_text.append(f' → {dns}\n', style='white')
            status_text.append(f'Status: ', style=self.colors['dim'])
            status_text.append(f'{status_label}\n', style=f'bold {color}')
            status_text.append(f'Created:  {created}\n', style=self.colors['dim'])
            status_text.append(f'Started:  {started}\n', style=self.colors['dim'])
            status_text.append(f'Finished: {finished}', style=self.colors['dim'])

            self.console.print(Panel(status_text, title='Job Status', border_style=color))

            # Show full results for completed/failed jobs
            if status_code in ('JP', 'JF'):
                self._render_job_results(job, cap)

        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_download(self, args):
        """Download job outputs, proofs, and files to a local directory."""
        import os

        # Parse arguments
        target = args[0] if args else 'all'
        output_dir = None
        for i, a in enumerate(args):
            if a in ('--output', '-o') and i + 1 < len(args):
                output_dir = args[i + 1]

        # Build output directory
        account_name = self.context.account or 'default'
        # Clean account name for filesystem
        safe_name = account_name.replace('@', '_at_').replace('+', '_')
        for c in '<>:"/\\|?*':
            safe_name = safe_name.replace(c, '_')

        if not output_dir:
            output_dir = os.path.join(os.getcwd(), 'guard-output', safe_name)

        os.makedirs(output_dir, exist_ok=True)

        if target == 'all':
            self.console.print(f'[info]Downloading all outputs to {output_dir}/[/info]')
            self._download_category('proofs', output_dir)
            self._download_category('agents', output_dir)
            self._download_category('definitions', output_dir)
        elif target == 'proofs':
            self.console.print(f'[info]Downloading proofs to {output_dir}/[/info]')
            self._download_category('proofs', output_dir)
        elif target == 'agents':
            self.console.print(f'[info]Downloading agent outputs to {output_dir}/[/info]')
            self._download_category('agents', output_dir)
        elif target == 'definitions':
            self.console.print(f'[info]Downloading definitions to {output_dir}/[/info]')
            self._download_category('definitions', output_dir)
        elif target == 'files':
            self.console.print(f'[info]Downloading all files to {output_dir}/[/info]')
            self._download_category('', output_dir)
        else:
            # Treat as a file path prefix to download
            self.console.print(f'[info]Downloading {target} to {output_dir}/[/info]')
            self._download_category(target, output_dir)

        self.console.print(f'[success]Downloads saved to {output_dir}/[/success]')

    def _download_category(self, prefix: str, output_dir: str):
        """Download all files matching a prefix to local directory."""
        import os

        try:
            files, _ = self.sdk.files.list(prefix, pages=10)
        except Exception as e:
            self.console.print(f'[error]Failed to list files: {e}[/error]')
            return

        if not files:
            self.console.print(f'[dim]No files found for: {prefix or "all"}[/dim]')
            return

        self.console.print(f'[dim]Found {len(files)} files...[/dim]')
        downloaded = 0
        errors = 0

        for f in files:
            file_key = f.get('key', '')
            # Extract the path from #file#<path>
            if file_key.startswith('#file#'):
                file_path = file_key[6:]  # strip #file#
            else:
                file_path = f.get('name', file_key)

            if not file_path or file_path.startswith('#'):
                continue

            # Build local path
            local_path = os.path.join(output_dir, file_path)
            local_dir = os.path.dirname(local_path)

            try:
                os.makedirs(local_dir, exist_ok=True)
                content = self.sdk.files.get(file_path)
                with open(local_path, 'wb') as fp:
                    fp.write(content)
                downloaded += 1
            except Exception:
                errors += 1

        self.console.print(f'[dim]  Downloaded: {downloaded}, Errors: {errors}[/dim]')

    def _cmd_info(self, args):
        if not args:
            self.console.print('[dim]Usage: info <key>[/dim]')
            return
        key = args[0]
        try:
            if '#risk#' in key:
                result = self.sdk.risks.get(key, details=True)
            elif '#asset#' in key:
                result = self.sdk.assets.get(key, details=True)
            else:
                result = self.sdk.search.by_exact_key(key, get_attributes=True)
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    # ── Operation commands ───────────────────────────────────────

    def _cmd_scan(self, args):
        if not args:
            self.console.print('[dim]Usage: scan <asset_key> [capability][/dim]')
            return
        asset_key = args[0]
        capabilities = args[1:] if len(args) > 1 else []
        try:
            result = self.sdk.jobs.add(asset_key, capabilities=capabilities)
            self.console.print(f'[success]Job queued[/success]')
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_tag(self, args):
        if len(args) < 2:
            self.console.print('[dim]Usage: tag <risk_key> <tag1> [tag2 ...][/dim]')
            return
        key = args[0]
        tags = args[1:]
        try:
            self.sdk.risks.update(key, tags=tags)
            self.console.print(f'[success]Tagged {key} with: {", ".join(tags)}[/success]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    # ── Security Tools ───────────────────────────────────────────

    def _cmd_run(self, args):
        """Run a named security tool against a target, or execute active tool."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        if not args and self.context.active_tool:
            # "run" with no args while tool is selected = execute
            self._cmd_execute([])
            return
        if not args:
            # Show agents
            agents = {k: v for k, v in TOOL_ALIASES.items() if v.get('agent') and k != 'secrets'}
            table = Table(title='Agents', border_style=self.colors['primary'])
            table.add_column('Agent', style=f'bold {self.colors["primary"]}', min_width=16)
            table.add_column('Description')
            for name, info in sorted(agents.items()):
                table.add_row(name, info['description'])
            self.console.print(table)

            # Show direct capabilities
            caps = {k: v for k, v in TOOL_ALIASES.items() if not v.get('agent') and k != 'secrets'}
            if caps:
                table2 = Table(title='Capabilities', border_style=self.colors['dim'])
                table2.add_column('Capability', style=f'bold {self.colors["primary"]}', min_width=16)
                table2.add_column('Target', style=self.colors['accent'])
                table2.add_column('Description')
                for name, info in sorted(caps.items()):
                    table2.add_row(name, info['target_type'], info['description'])
                self.console.print(table2)

            self.console.print(f'\n[dim]Usage: use <name> or <name> <target_key>[/dim]')
            return

        tool_name = args[0].lower()
        alias = TOOL_ALIASES.get(tool_name)
        if not alias:
            available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
            self.console.print(f'[error]Unknown tool: {tool_name}. Available: {available}[/error]')
            return

        if len(args) < 2:
            self.console.print(f'[dim]Usage: {tool_name} <target_key> [--ask] [--wait][/dim]')
            self.console.print(f'[dim]  Target type: {alias["target_type"]}[/dim]')
            self.console.print(f'[dim]  {alias["description"]}[/dim]')
            return

        raw_target = args[1]
        use_agent = '--ask' in args
        wait = '--wait' in args

        # Resolve friendly target names to Guard keys
        from praetorian_cli.handlers.run import resolve_target
        target_key, warning = resolve_target(self.sdk, raw_target, alias['target_type'])
        if not target_key:
            self.console.print(f'[error]{warning}[/error]')
            return
        if warning:
            self.console.print(f'[warning]{warning}[/warning]')

        capability = alias.get('capability')
        config = dict(alias.get('default_config', {}))

        if alias.get('agent') and (use_agent or not capability):
            # Route through Marcus (forced for agent-only tools, optional for others)
            agent_name = alias['agent']
            task_desc = f'Run {capability} against {target_key} and analyze the results.' if capability else f'Analyze {target_key} thoroughly.'
            message = self.context.apply_scope_to_message(task_desc)
            self.console.print(f'[info]Delegating to {agent_name} via Marcus...[/info]')
            response_text = self._send_to_marcus(message)
            if response_text:
                self.console.print(Markdown(response_text))
        else:
            # Direct job execution — with fallback to own account if frozen/blocked
            config_str = json.dumps(config) if config else None
            result = self._try_queue_job(target_key, capability, config_str)
            if result is None:
                return

            if wait:
                self._wait_for_job(target_key, capability)

    def _try_queue_job(self, target_key, capability, config_str):
        """Try to queue a job. If frozen/blocked, fallback to the login user's own account."""
        # First attempt
        first_error = None
        try:
            result = self.sdk.jobs.add(target_key, [capability], config_str)
        except Exception as e:
            first_error = e

        if first_error is None:
            # Success on first try
            pass
        else:
            error_msg = str(first_error).lower()
            is_frozen = 'frozen' in error_msg or 'blocked' in error_msg

            if not is_frozen:
                self.console.print(f'[error]{first_error}[/error]')
                return None

            # Frozen/blocked — fallback by clearing impersonation
            login_user = None
            try:
                login_user = self.sdk.accounts.login_principal()
            except Exception:
                pass
            display_user = login_user or 'API key owner'

            self.console.print(f'[dim]Account frozen — retrying as {display_user}[/dim]')
            saved = self.sdk.keychain.account
            self.sdk.keychain.account = None
            try:
                result = self.sdk.jobs.add(target_key, [capability], config_str)
            except Exception as e2:
                self.console.print(f'[error]Fallback also failed: {e2}[/error]')
                return None
            finally:
                self.sdk.keychain.account = saved

        job_key = ''
        if isinstance(result, list) and result:
            job_key = result[0].get('key', '')
        elif isinstance(result, dict):
            job_key = result.get('key', '')
        self.context._last_job_key = job_key
        self.console.print(f'[success]Job queued: {capability} → {target_key}[/success]')
        self.console.print(f'[dim]Job key: {job_key}[/dim]')
        self.console.print(f'[dim]Use "status" to check progress, or "run --wait" to wait for results.[/dim]')
        return result

    def _wait_for_job(self, target_key, capability):
        """Poll for job completion and show results."""
        max_wait = 300
        start_time = time.time()
        with self.console.status('Waiting for job...', spinner='dots', spinner_style=self.colors['primary']) as status:
            while time.time() - start_time < max_wait:
                try:
                    jobs, _ = self.sdk.jobs.list(target_key.lstrip('#'))
                    matching = [j for j in jobs if capability in j.get('source', '') or capability in j.get('key', '')]
                    if matching:
                        latest = sorted(matching, key=lambda j: j.get('created', 0), reverse=True)[0]
                        st = latest.get('status', '')
                        if st.startswith('JP'):
                            elapsed = int(time.time() - start_time)
                            self.console.print(f'\n[success]Job completed in {elapsed}s[/success]')
                            self._render_job_results(latest, capability)
                            return
                        elif st.startswith('JF'):
                            self.console.print(f'\n[error]Job failed.[/error]')
                            self._render_job_results(latest, capability)
                            return
                        else:
                            elapsed = int(time.time() - start_time)
                            status.update(f'{capability} running ({elapsed}s)...')
                except Exception:
                    pass
                time.sleep(5)
        self.console.print('[warning]Timed out waiting for job (5 min).[/warning]')

    def _render_job_results(self, job: dict, capability: str):
        """Render rich results from a completed job — findings, assets, ports, attributes."""
        job_key = job.get('key', '')
        dns = job.get('dns', '')
        status_code = job.get('status', '')[:2]

        # Fetch all results produced by this job
        risks = []
        assets = []
        attributes = []
        try:
            risks, _ = self.sdk.search.by_source(job_key, 'risk')
        except Exception:
            pass
        try:
            assets, _ = self.sdk.search.by_source(job_key, 'asset')
        except Exception:
            pass
        try:
            attributes, _ = self.sdk.search.by_source(job_key, 'attribute')
        except Exception:
            pass

        # Build summary
        summary_parts = []
        if risks:
            summary_parts.append(f'{len(risks)} finding(s)')
        if assets:
            summary_parts.append(f'{len(assets)} asset(s) discovered')
        if attributes:
            summary_parts.append(f'{len(attributes)} attribute(s)')
        if not summary_parts:
            summary_parts.append('no new results')

        color = self.colors['success'] if status_code == 'JP' else self.colors['error']
        status_label = 'PASSED' if status_code == 'JP' else 'FAILED'

        header = Text()
        header.append(f'{capability}', style=f'bold {self.colors["primary"]}')
        header.append(f' → {dns}\n', style='white')
        header.append(f'Status: ', style=self.colors['dim'])
        header.append(f'{status_label}', style=f'bold {color}')
        header.append(f' — {", ".join(summary_parts)}', style=self.colors['dim'])
        self.console.print(Panel(header, title='Job Complete', border_style=color))

        # Show discovered assets (e.g., from portscan, subdomain)
        if assets:
            table = Table(title=f'Discovered Assets ({len(assets)})', border_style=self.colors['primary'])
            table.add_column('Key', style=self.colors['primary'])
            table.add_column('Name', style='white')
            table.add_column('Class', style=self.colors['accent'])
            table.add_column('Status', style=self.colors['dim'])
            for a in assets[:20]:
                table.add_row(
                    a.get('key', ''), a.get('name', a.get('dns', '')),
                    a.get('class', ''), a.get('status', ''),
                )
            self.console.print(table)
            if len(assets) > 20:
                self.console.print(f'[dim]...and {len(assets) - 20} more[/dim]')

        # Show attributes (e.g., open ports from portscan)
        if attributes:
            table = Table(title=f'Attributes ({len(attributes)})', border_style=self.colors['primary'])
            table.add_column('Name', style=f'bold {self.colors["primary"]}')
            table.add_column('Value', style='white')
            for attr in attributes[:30]:
                table.add_row(attr.get('name', ''), str(attr.get('value', '')))
            self.console.print(table)
            if len(attributes) > 30:
                self.console.print(f'[dim]...and {len(attributes) - 30} more[/dim]')

        # Show findings/risks
        if risks:
            table = Table(title=f'Findings ({len(risks)})', border_style=self.colors['error'])
            table.add_column('Risk', style=f'bold {self.colors["primary"]}')
            table.add_column('Severity', style=self.colors['accent'])
            table.add_column('Asset', style='white')
            table.add_column('Status', style=self.colors['dim'])
            for r in risks[:20]:
                name = r.get('name', r.get('title', ''))
                priority = r.get('priority', '')
                severity_map = {0: 'CRITICAL', 10: 'HIGH', 20: 'MEDIUM', 30: 'LOW', 40: 'INFO', 60: 'EXPOSURE'}
                severity = severity_map.get(priority, str(priority))
                table.add_row(name, severity, r.get('dns', ''), r.get('status', ''))
            self.console.print(table)
            if len(risks) > 20:
                self.console.print(f'[dim]...and {len(risks) - 20} more[/dim]')

    def _cmd_install(self, args):
        """Install a capability binary locally from GitHub."""
        from praetorian_cli.runners.local import install_tool, INSTALLABLE_TOOLS, is_installed
        if not args:
            self.console.print('[dim]Usage: install <tool_name|all>[/dim]')
            self.console.print(f'[dim]Available: {", ".join(sorted(INSTALLABLE_TOOLS))}[/dim]')
            return
        tool_name = args[0].lower()
        force = '--force' in args
        if tool_name == 'all':
            for name in sorted(INSTALLABLE_TOOLS):
                try:
                    if not force and is_installed(name):
                        self.console.print(f'  {name}: [dim]already installed[/dim]')
                    else:
                        with self.console.status(f'Installing {name}...', spinner='dots', spinner_style=self.colors['primary']):
                            path = install_tool(name, force=force)
                        self.console.print(f'  {name}: [success]{path}[/success]')
                except Exception as e:
                    self.console.print(f'  {name}: [error]{e}[/error]')
        else:
            try:
                with self.console.status(f'Installing {tool_name}...', spinner='dots', spinner_style=self.colors['primary']):
                    path = install_tool(tool_name, force=force)
                self.console.print(f'[success]Installed: {path}[/success]')
            except Exception as e:
                self.console.print(f'[error]{e}[/error]')

    def _cmd_installed(self, args):
        """List locally installed capability binaries."""
        from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS
        inst = list_installed()
        table = Table(title='Local Binaries', border_style=self.colors['primary'])
        table.add_column('Tool', style=f'bold {self.colors["primary"]}', min_width=16)
        table.add_column('Status', min_width=10)
        table.add_column('Path', style=self.colors['dim'])
        for name in sorted(INSTALLABLE_TOOLS):
            if name in inst:
                table.add_row(name, f'[success]installed[/success]', inst[name])
            else:
                table.add_row(name, f'[dim]—[/dim]', '')
        self.console.print(table)

    def _cmd_capabilities(self, args):
        """List available capabilities from the backend."""
        name_filter = args[0] if args else ''
        try:
            result = self.sdk.capabilities.list(name=name_filter)
            # result can be a list directly or a dict with a key
            if isinstance(result, list):
                caps = result
            elif isinstance(result, dict):
                caps = result.get('capabilities', result.get('data', []))
            elif isinstance(result, tuple):
                caps = result[0] if result[0] else []
            else:
                caps = []

            if isinstance(caps, list) and caps:
                table = Table(title=f'Capabilities ({len(caps)})', border_style=self.colors['primary'])
                table.add_column('Name', style=f'bold {self.colors["primary"]}')
                table.add_column('Target', style=self.colors['accent'])
                table.add_column('Executor', style=self.colors['dim'])
                table.add_column('Description')
                for cap in caps:
                    if isinstance(cap, dict):
                        name = str(cap.get('name', cap.get('Name', '')))
                        target = cap.get('target', cap.get('Target', ''))
                        if isinstance(target, list):
                            target = ','.join(target)
                        desc = str(cap.get('description', cap.get('Description', '')))[:50]
                        executor = str(cap.get('executor', ''))
                        table.add_row(name, str(target), executor, desc)
                self.console.print(table)
            else:
                self.console.print('[dim]No capabilities found.[/dim]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    # ── Evidence & Reporting ─────────────────────────────────────

    def _cmd_evidence(self, args):
        if not args:
            self.console.print('[dim]Usage: evidence <risk_key>[/dim]')
            return
        key = args[0]
        try:
            result = self.sdk.risks.hydrate_evidence(key)
            self._render_evidence(result)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_report(self, args):
        if not args:
            self.console.print('[dim]Usage: report <generate|validate> [options][/dim]')
            return
        subcmd = args[0].lower()
        if subcmd == 'generate':
            self._report_generate(args[1:])
        elif subcmd == 'validate':
            self._report_validate(args[1:])
        else:
            self.console.print(f'[dim]Unknown report subcommand: {subcmd}[/dim]')

    def _report_generate(self, args):
        body = {'format': 'pdf'}
        i = 0
        while i < len(args):
            if args[i] == '--title' and i + 1 < len(args):
                body['title'] = args[i + 1]; i += 2
            elif args[i] == '--client' and i + 1 < len(args):
                body['client'] = args[i + 1]; i += 2
            elif args[i] == '--risks' and i + 1 < len(args):
                body['risks'] = args[i + 1]; i += 2
            elif args[i] == '--group-by-phase':
                body['groupByPhase'] = True; i += 1
            elif args[i] == '--format' and i + 1 < len(args):
                body['format'] = args[i + 1]; i += 2
            else:
                i += 1
        try:
            result = self.sdk.post('export/report', body)
            self.console.print(f'[success]Report generated[/success]')
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]Report generation failed: {e}[/error]')

    def _report_validate(self, args):
        body = {}
        i = 0
        while i < len(args):
            if args[i] == '--risks' and i + 1 < len(args):
                body['risks'] = args[i + 1]; i += 2
            elif args[i] == '--include-narratives':
                body['includeNarratives'] = True; i += 1
            else:
                i += 1
        try:
            result = self.sdk.post('validate-report', body)
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]Validation failed: {e}[/error]')

    # ── Marcus / AI ──────────────────────────────────────────────

    def _cmd_ask(self, args):
        if not args:
            self.console.print('[dim]Usage: ask "<question>"[/dim]')
            return

        message = ' '.join(args)
        if message.startswith('--new'):
            self.context.clear_conversation()
            message = ' '.join(args[1:])

        message = self.context.apply_scope_to_message(message)
        response_text = self._send_to_marcus(message)

        if response_text:
            self.console.print(Panel(
                Markdown(response_text),
                title='Marcus',
                border_style=self.colors['primary'],
            ))

    def _cmd_marcus(self, args):
        """Marcus subcommands or multi-turn conversation mode."""
        # Handle subcommands: marcus read, marcus ingest, marcus do
        if args and args[0].lower() == 'read':
            self._marcus_read(args[1:])
            return
        if args and args[0].lower() == 'ingest':
            self._marcus_ingest(args[1:])
            return
        if args and args[0].lower() == 'do':
            self._marcus_do(args[1:])
            return

        if args and args[0] == '--new':
            self.context.clear_conversation()
        if args and args[0] == '--query':
            self.context.mode = 'query'

        self.console.print(f'[primary]Entering conversation mode[/primary] [dim](type "back" to return)[/dim]')
        self.console.print(f'[dim]Commands: read <path>, ingest <path>, do "<instruction>", or just chat[/dim]')
        self.console.print(f'[dim]Context: {self.context.summary()}[/dim]\n')

        while True:
            try:
                marcus_prompt = HTML(
                    f'<style fg="{COMPLEMENTARY_GOLD}" bg="">marcus</style>'
                    f' <style fg="{PRIMARY_RED}" bg="">&gt;</style> '
                )
                user_input = self.session.prompt(marcus_prompt).strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input:
                continue
            if user_input.lower() in ('back', 'quit', 'exit'):
                break
            if user_input.lower() == 'new':
                self.context.clear_conversation()
                self.console.print('[success]New conversation started[/success]')
                continue
            if user_input.lower() in ('query', 'agent'):
                self.context.mode = user_input.lower()
                self.console.print(f'[success]Switched to {user_input.lower()} mode[/success]')
                continue
            if user_input.startswith('@'):
                self.context.active_agent = user_input[1:]
                self.console.print(f'[success]Active agent: {self.context.active_agent}[/success]')
                continue

            message = self.context.apply_scope_to_message(user_input)
            response_text = self._send_to_marcus(message)
            if response_text:
                self.console.print(Markdown(response_text))
                self.console.print()

        self.console.print('[dim]Returned to console.[/dim]')

    def _send_to_marcus(self, message: str) -> Optional[str]:
        """Send message to Marcus and poll for response with live tool output."""
        url = self.sdk.url('/planner')
        payload = {'message': message, 'mode': self.context.mode}
        if self.context.conversation_id:
            payload['conversationId'] = self.context.conversation_id

        with self.console.status('Sending...', spinner='dots', spinner_style=self.colors['primary']):
            response = self.sdk.chariot_request('POST', url, json=payload)

        # If AI is disabled on the impersonated account, retry as the Praetorian user
        if response.status_code == 403 and self.context.account:
            login_user = self.sdk.accounts.login_principal()
            if login_user and login_user.endswith('@praetorian.com'):
                self.console.print(f'[dim]AI not enabled on this account — routing through {login_user}[/dim]')
                # Temporarily clear impersonation for the AI call
                saved_account = self.sdk.keychain.account
                self.sdk.keychain.account = None
                # Add engagement context to the message so Marcus queries the right data
                if self.context.account not in message:
                    message = f'[Context: querying data for account {self.context.account}] {message}'
                payload['message'] = message
                if self.context.conversation_id:
                    payload.pop('conversationId', None)
                    self.context.conversation_id = None
                with self.console.status('Sending via Praetorian account...', spinner='dots', spinner_style=self.colors['primary']):
                    response = self.sdk.chariot_request('POST', url, json=payload)
                self.sdk.keychain.account = saved_account

        if not response.ok:
            self.console.print(f'[error]API error: {response.status_code} - {response.text}[/error]')
            return None

        result = response.json()
        if not self.context.conversation_id and 'conversation' in result:
            self.context.conversation_id = result['conversation'].get('uuid')

        # Snapshot existing messages so we only process NEW ones from this request
        last_key = ''
        try:
            existing, _ = self.sdk.search.by_key_prefix(
                f'#message#{self.context.conversation_id}#', user=True
            )
            if existing:
                last_key = max(m.get('key', '') for m in existing)
        except Exception:
            pass

        # Poll for response — show tool calls live
        max_wait = 180
        start_time = time.time()
        pending_tool = None

        self.console.print(f'[dim]Thinking...[/dim]', end='')

        while time.time() - start_time < max_wait:
            try:
                messages, _ = self.sdk.search.by_key_prefix(
                    f'#message#{self.context.conversation_id}#', user=True
                )
                new_msgs = sorted(
                    [m for m in messages if m.get('key', '') > last_key],
                    key=lambda x: x.get('key', '')
                )

                for msg in new_msgs:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    last_key = msg.get('key', '')

                    if role == 'chariot':
                        if pending_tool:
                            self.console.print()  # newline after tool output
                        return content
                    elif role == 'tool call':
                        # Parse tool call content for display
                        tool_name = self._parse_tool_name(content, msg)
                        if pending_tool:
                            self.console.print(f' [success]done[/success]')
                        self.console.print(f'  [dim]→[/dim] [accent]{tool_name}[/accent]', end='')
                        pending_tool = tool_name
                    elif role == 'tool response':
                        # Show result summary
                        result_summary = self._parse_tool_result(content)
                        if result_summary:
                            self.console.print(f' [dim]— {result_summary}[/dim]', end='')
                        self.console.print(f' [success]done[/success]')
                        pending_tool = None
            except Exception:
                pass

            time.sleep(1)

        self.console.print('\n[warning]Timed out waiting for response[/warning]')
        return None

    def _parse_tool_name(self, content: str, msg: dict = None) -> str:
        """Extract a human-readable tool name from a tool call message."""
        # Try toolUseContent field first (structured tool input)
        tool_content = msg.get('toolUseContent', '') if msg else ''
        # Try the message name field (some backends store tool name there)
        msg_name = msg.get('name', '') if msg else ''
        if msg_name and msg_name not in ('user', 'chariot', 'tool call', 'tool response'):
            return msg_name

        for raw in (tool_content, content):
            if not raw:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict):
                    name = data.get('name', data.get('tool', data.get('type', '')))
                    if name:
                        inp = data.get('input', data.get('arguments', {}))
                        if isinstance(inp, dict):
                            if 'capability' in inp:
                                return f'{name}({inp["capability"]})'
                            if 'agent' in inp:
                                return f'{name}({inp["agent"]})'
                        return str(name)
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        return 'tool'

    def _parse_tool_result(self, content: str) -> str:
        """Extract a brief summary from a tool response message."""
        try:
            data = json.loads(content) if isinstance(content, str) else content
            if isinstance(data, dict):
                # Count results if it looks like a query response
                for key in ('assets', 'risks', 'data', 'results', 'seeds', 'jobs'):
                    if key in data and isinstance(data[key], list):
                        return f'{len(data[key])} {key}'
                if 'status' in data:
                    return f'status: {data["status"]}'
                if 'error' in data:
                    return f'error: {str(data["error"])[:50]}'
            elif isinstance(data, list):
                return f'{len(data)} results'
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return ''

    # ── Marcus subcommands ────────────────────────────────────────

    def _marcus_read(self, args):
        """Have Marcus read and analyze a file."""
        if not args:
            self.console.print('[dim]Usage: marcus read <guard_path> [--local][/dim]')
            self.console.print('[dim]  guard_path: file in Guard storage (e.g., vault/sow.pdf, proofs/screenshot.png)[/dim]')
            self.console.print('[dim]  --local: path is a local file (uploads to Guard first)[/dim]')
            return

        path = args[0]
        is_local = '--local' in args
        instructions = ''
        if '-i' in args:
            idx = args.index('-i')
            if idx + 1 < len(args):
                instructions = ' '.join(args[idx + 1:])

        if is_local:
            import os
            if not os.path.exists(path):
                self.console.print(f'[error]Local file not found: {path}[/error]')
                return
            filename = os.path.basename(path)
            guard_path = f'home/{filename}'
            with self.console.status(f'Uploading {path}...', spinner='dots', spinner_style=self.colors['primary']):
                self.sdk.files.add(path, guard_path)
            self.console.print(f'[success]Uploaded to {guard_path}[/success]')
            path = guard_path

        base = f'Read the file at "{path}" using the file_read tool.'
        if instructions:
            message = f'{base} {instructions}'
        else:
            message = (
                f'{base} Analyze its contents and tell me what you found. '
                f'If it contains scope info (domains, IPs, CIDRs), offer to add them as seeds. '
                f'If it contains vulnerability findings, offer to create risks. '
                f'If it contains credentials or secrets, flag them.'
            )

        message = self.context.apply_scope_to_message(message)
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus', border_style=self.colors['primary']))

    def _marcus_ingest(self, args):
        """Have Marcus read a file and automatically ingest data into Guard."""
        if not args:
            self.console.print('[dim]Usage: marcus ingest <guard_path> [--scope] [--findings][/dim]')
            return

        path = args[0]
        scope = '--scope' in args
        findings = '--findings' in args

        actions = []
        if scope:
            actions.append('Add any discovered domains, IPs, and CIDRs as seeds using seed_add.')
        if findings:
            actions.append('Create risks for any vulnerability findings you identify.')
        if not actions:
            actions.append('Add scope items as seeds and create risks for any findings.')

        message = (
            f'Read the file at "{path}" using the file_read tool. '
            f'Analyze its contents thoroughly. {" ".join(actions)} '
            f'Take action automatically — do not ask for confirmation. '
            f'Report what you created when done.'
        )

        message = self.context.apply_scope_to_message(message)
        self.console.print(f'[info]Marcus is reading and ingesting {path}...[/info]')
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus — Ingestion Complete', border_style=self.colors['primary']))

    def _marcus_do(self, args):
        """Give Marcus a direct instruction to execute."""
        if not args:
            self.console.print('[dim]Usage: marcus do "<instruction>"[/dim]')
            self.console.print('[dim]  Examples:[/dim]')
            self.console.print('[dim]    marcus do "add example.com as a seed and start discovery"[/dim]')
            self.console.print('[dim]    marcus do "run nuclei on all assets with port 443"[/dim]')
            self.console.print('[dim]    marcus do "generate an executive summary"[/dim]')
            return

        instruction = ' '.join(args)
        message = self.context.apply_scope_to_message(instruction)
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus', border_style=self.colors['primary']))

    # ── Aegis ────────────────────────────────────────────────────

    def _cmd_aegis(self, args):
        try:
            from praetorian_cli.ui.aegis.menu import AegisMenu
            menu = AegisMenu(self.sdk)
            menu.run()
        except ImportError:
            self.console.print('[error]Aegis module not available[/error]')
        except Exception as e:
            self.console.print(f'[error]Aegis error: {e}[/error]')

    # ── Utility commands ─────────────────────────────────────────

    def _cmd_help(self, args):
        help_table = Table(title='Guard Console Commands', border_style=self.colors['primary'])
        help_table.add_column('Command', style=f'bold {self.colors["primary"]}', min_width=25)
        help_table.add_column('Description')

        help_table.add_row('[heading]Context[/heading]', '')
        help_table.add_row('set account <email>', 'Set engagement account')
        help_table.add_row('set scope <pattern>', 'Filter to domain/asset group')
        help_table.add_row('set mode <query|agent>', 'Set Marcus conversation mode')
        help_table.add_row('unset scope', 'Clear scope filter')
        help_table.add_row('show context', 'Display current engagement state')
        help_table.add_row('accounts / engagements', 'List accounts you can access')
        help_table.add_row('engagements use <#>', 'Switch to engagement (shows stats)')
        help_table.add_row('switch <# or email>', 'Switch to engagement (shows stats)')
        help_table.add_row('home / su', 'Return to your own account')
        help_table.add_row('engagements create email=... name=...', 'Create new customer')
        help_table.add_row('engagements vault client=... sow=... sku=... github-user=...', 'Create vault repo')
        help_table.add_row('engagements onboard email=... name=... seed=...', 'Full onboarding')

        help_table.add_row('', '')
        help_table.add_row('[heading]Search & Recon[/heading]', '')
        help_table.add_row('search <term>', 'Fast prefix search (DynamoDB)')
        help_table.add_row('find <term> [--type X]', 'Fulltext search (Neo4j)')
        help_table.add_row('assets', 'List assets (respects scope)')
        help_table.add_row('risks', 'List risks (respects scope)')
        help_table.add_row('jobs [filter]', 'List jobs (filter by target/capability)')
        help_table.add_row('status', 'Check status of last job')
        help_table.add_row('status <job_key>', 'Check status of specific job')
        help_table.add_row('download [proofs|agents|all]', 'Download job outputs to local dir')
        help_table.add_row('download <prefix> -o <dir>', 'Download specific files to dir')
        help_table.add_row('info <key>', 'Get entity details')

        help_table.add_row('', '')
        help_table.add_row('[heading]Operations[/heading]', '')
        help_table.add_row('scan <asset> [cap]', 'Schedule a scan job')
        help_table.add_row('tag <risk> <tag...>', 'Tag a risk')

        help_table.add_row('', '')
        help_table.add_row('[heading]Security Tools (Metasploit-style)[/heading]', '')
        help_table.add_row('use <tool>', 'Select a tool (brutus, nuclei, julius, etc.)')
        help_table.add_row('show targets', 'Show valid targets for active tool')
        help_table.add_row('set target <key|#>', 'Set target (key or number from list)')
        help_table.add_row('options', 'Show current tool options')
        help_table.add_row('execute / exploit', 'Run the active tool against the target')
        help_table.add_row('back', 'Deselect current tool')
        help_table.add_row('', '')
        help_table.add_row('[heading]Agents & Capabilities[/heading]', '')
        help_table.add_row('asset-analyzer <key>', 'Deep-dive recon & risk mapping')
        help_table.add_row('brutus <port_key>', 'Credential attacks (SSH, RDP, FTP, SMB)')
        help_table.add_row('julius <port_key>', 'LLM/AI service fingerprinting')
        help_table.add_row('augustus <webpage_key>', 'LLM jailbreak & injection attacks')
        help_table.add_row('aurelius <asset_key>', 'Cloud infrastructure discovery')
        help_table.add_row('trajan <asset_key>', 'CI/CD pipeline security scanning')
        help_table.add_row('cato <risk_key>', 'Finding validation & triage')
        help_table.add_row('priscus <risk_key>', 'Remediation retesting')
        help_table.add_row('seneca <risk_key>', 'CVE research & exploit intelligence')
        help_table.add_row('titus <repo_key>', 'Secret scanning & credential leak detection')
        help_table.add_row('nuclei <asset_key>', 'Vulnerability scanner')
        help_table.add_row('portscan <asset_key>', 'Port scanning')
        help_table.add_row('capabilities [name]', 'List all backend capabilities')
        help_table.add_row('install <tool|all>', 'Install binary from GitHub')
        help_table.add_row('installed', 'List locally installed binaries')

        help_table.add_row('', '')
        help_table.add_row('[heading]Evidence & Reports[/heading]', '')
        help_table.add_row('evidence <risk_key>', 'Hydrated evidence for a risk')
        help_table.add_row('report generate [opts]', 'Generate engagement report')
        help_table.add_row('report validate [opts]', 'Validate report requirements')

        help_table.add_row('', '')
        help_table.add_row('[heading]Marcus Aurelius[/heading]', '')
        help_table.add_row('ask "<question>"', 'One-shot query to Marcus')
        help_table.add_row('marcus', 'Enter multi-turn conversation')
        help_table.add_row('marcus read <path>', 'Read & analyze a file (vault, proofs, etc.)')
        help_table.add_row('marcus ingest <path>', 'Read file & auto-create seeds/risks')
        help_table.add_row('marcus do "<instruction>"', 'Direct instruction (full agent access)')

        help_table.add_row('', '')
        help_table.add_row('[heading]Other[/heading]', '')
        help_table.add_row('aegis', 'Open Aegis agent manager')
        help_table.add_row('clear', 'Clear screen')
        help_table.add_row('help', 'Show this help')
        help_table.add_row('quit', 'Exit console')

        self.console.print(help_table)

    def _cmd_configure(self, args):
        """Configure API keys — runs inline in the console."""
        from praetorian_cli.sdk.keychain import Keychain, DEFAULT_API, DEFAULT_CLIENT_ID, DEFAULT_PROFILE
        try:
            api_key_id = self.session.prompt(
                HTML(f'<style fg="{COMPLEMENTARY_GOLD}">API Key ID: </style>')
            ).strip()
            api_key_secret = self.session.prompt(
                HTML(f'<style fg="{COMPLEMENTARY_GOLD}">API Key Secret: </style>'),
                is_password=True,
            ).strip()

            if not api_key_id or not api_key_secret:
                self.console.print('[error]API Key ID and Secret are required.[/error]')
                return

            profile = DEFAULT_PROFILE
            Keychain.configure(
                username=None,
                password=None,
                profile=profile,
                api=DEFAULT_API,
                client_id=DEFAULT_CLIENT_ID,
                account=None,
                api_key_id=api_key_id,
                api_key_secret=api_key_secret,
            )
            self.console.print(f'[success]Configured. Profile: {profile}[/success]')
            self.console.print(f'[dim]Restart the console to use the new credentials.[/dim]')
        except (KeyboardInterrupt, EOFError):
            self.console.print('\n[dim]Cancelled.[/dim]')

    def _cmd_clear(self, args):
        self.console.clear()

    def _cmd_quit_or_back(self, args):
        """Exit does 'back' in subshells, quits at root prompt."""
        if self.context.active_tool:
            self._cmd_back(args)
        else:
            raise EOFError()

    def _cmd_quit(self, args):
        raise EOFError()

    # ── Rendering helpers ────────────────────────────────────────

    def _render_results(self, results: list, title: str):
        if not results:
            self.console.print(f'[dim]No results for: {title}[/dim]')
            if self.context.scope:
                self.console.print(f'[dim]Current scope: {self.context.scope} — use "unset scope" to broaden[/dim]')
            return

        table = Table(title=f'{title} ({len(results)} results)', border_style=self.colors['primary'])
        table.add_column('#', style=self.colors['dim'], width=4)
        table.add_column('Key', style=self.colors['primary'])
        table.add_column('Name', style='white')
        table.add_column('Status', style=self.colors['accent'])

        # Update _target_list so "set target <#>" works from any listing
        self._target_list = []
        for i, item in enumerate(results[:100], 1):
            key = item.get('key', '')
            name = item.get('name', item.get('dns', item.get('title', '')))
            status = item.get('status', '')
            table.add_row(str(i), key, str(name), status)
            self._target_list.append(key)

        self.console.print(table)
        if len(results) > 100:
            self.console.print(f'[dim]Showing first 100 of {len(results)} results[/dim]')

    def _render_evidence(self, hydrated: dict):
        risk = hydrated.get('risk', {})
        definition = hydrated.get('definition')
        evidence = hydrated.get('evidence', [])
        affected = hydrated.get('affected_assets', [])

        # Header
        self.console.print(Panel(
            f"[bold]{risk.get('name', 'Unknown')}[/bold]\n"
            f"Status: {risk.get('status', '?')} | Asset: {risk.get('dns', '?')} | Source: {risk.get('source', '?')}",
            title='Risk Detail',
            border_style=self.colors['primary'],
        ))

        # Definition sections
        if definition:
            if definition.get('description'):
                self.console.print(f'\n[heading]DESCRIPTION[/heading]')
                self.console.print(Markdown(definition['description']))
            if definition.get('impact'):
                self.console.print(f'\n[heading]IMPACT[/heading]')
                self.console.print(Markdown(definition['impact']))
            if definition.get('recommendation'):
                self.console.print(f'\n[heading]RECOMMENDATION[/heading]')
                self.console.print(Markdown(definition['recommendation']))

        # Evidence
        if evidence:
            self.console.print(f'\n[heading]EVIDENCE ({len(evidence)} sources)[/heading]')
            for ev in evidence:
                src = ev.get('source', '?')
                if src == 'attribute':
                    self.console.print(f"  [dim][attribute][/dim] {ev.get('name')}: {ev.get('value')}")
                elif src == 'webpage':
                    self.console.print(f"  [dim][webpage][/dim]   {ev.get('url', '?')}")
                elif src == 'file':
                    self.console.print(f"  [dim][file][/dim]      {ev.get('path', '?')} ({ev.get('size', '?')})")

        # References
        if definition and definition.get('references'):
            self.console.print(f'\n[heading]REFERENCES[/heading]')
            for ref in definition['references']:
                self.console.print(f'  - {ref}')

        # Affected assets
        if affected:
            self.console.print(f'\n[heading]AFFECTED ASSETS ({len(affected)})[/heading]')
            for asset in affected[:10]:
                self.console.print(f"  {asset.get('key', '?')}")
            if len(affected) > 10:
                self.console.print(f'  [dim]...and {len(affected) - 10} more[/dim]')


def run_console(sdk: Chariot, account: Optional[str] = None):
    """Entry point for the interactive console."""
    console = GuardConsole(sdk, account=account)
    console.run()
