"""Context commands: set/unset/show/use/options/execute/back. Mixed into GuardConsole."""

import json

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class ContextCommands:
    """Context-related console commands. Mixed into GuardConsole."""

    def _cmd_set(self, args):
        if len(args) < 2:
            self.console.print('[dim]Usage: set <account|scope|mode|target> <value>[/dim]')
            return
        key, value = args[0].lower(), ' '.join(args[1:]).strip().rstrip('.')
        if key == 'account':
            # Always validate against the real account list
            if not (hasattr(self, '_account_list') and self._account_list):
                try:
                    accounts_list, _ = self.sdk.accounts.list()
                    self._account_list = [a.get('name', '') for a in (accounts_list or [])]
                except Exception:
                    self._account_list = []
            if self._account_list and value not in self._account_list:
                self.console.print(f'[error]Unknown account: {value}[/error]')
                self.console.print(f'[dim]Run "accounts" to see the list, or "switch <#>" to select by number.[/dim]')
                return
            self.context.account = value
            self.context.clear_conversation()
            self.context.clear_tool()
            # Update SDK impersonation so all API calls use this account
            self.sdk.keychain.account = value
            # Clear stale target lists from previous engagement
            self._target_list = []
            self.console.print(f'[success]Account set to {value}[/success]')
            self._show_engagement_status()
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
        elif key == 'verbose':
            if value.lower() in ('on', 'true', '1', 'yes'):
                self.context.verbose = True
                self.console.print('[success]Verbose mode ON -- tool calls will show full details[/success]')
            elif value.lower() in ('off', 'false', '0', 'no'):
                self.context.verbose = False
                self.console.print('[success]Verbose mode OFF[/success]')
            else:
                self.console.print('[error]Usage: set verbose on|off[/error]')
        else:
            self.console.print(f'[dim]Unknown setting: {key}. Use: account, scope, mode, target, verbose[/dim]')

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
            table.add_row('Verbose', 'on' if self.context.verbose else '[dim]off[/dim]')
            table.add_row('Agent', self.context.active_agent or '[dim]default[/dim]')
            table.add_row('Conversation', self.context.conversation_id[:8] + '...' if self.context.conversation_id else '[dim]none[/dim]')
            self.console.print(table)
        elif target in ('targets', 'hosts'):
            self._show_targets()
        elif target in ('options', 'info'):
            self._cmd_options(args[1:])
        elif target == 'tools':
            self._cmd_run([])
        elif target in ('calls', 'toolcalls'):
            self._show_tool_calls()
        elif target == 'assets':
            self._cmd_assets(args[1:])
        elif target == 'risks':
            self._cmd_risks(args[1:])
        elif target == 'jobs':
            self._cmd_jobs(args[1:])
        elif target in ('accounts', 'engagements'):
            self._cmd_accounts(args[1:])
        elif target.isdigit():
            # "show 1" -- show detail of item # from last listing
            self._show_detail_by_number(int(target))
        else:
            self.console.print(f'[dim]Unknown: show {target}. Try: context, targets, assets, risks, jobs, tools, options, or a number.[/dim]')

    def _show_targets(self):
        """Show available targets (assets/seeds/ports) for the active tool."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        from praetorian_cli.sdk.model.query import Query, Node

        alias = TOOL_ALIASES.get(self.context.active_tool) if self.context.active_tool else None
        target_type = alias['target_type'] if alias else 'asset'

        with self.console.status('Fetching targets...', spinner='dots', spinner_style=self.colors['primary']):
            try:
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
                self.console.print(f'[dim]Scope: {self.context.scope} -- use "unset scope" to broaden[/dim]')
            return

        table = Table(
            title=f'Available Targets ({target_type}) -- {len(results)} found',
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

    def _show_tool_calls(self):
        """Show tool calls from the last Marcus interaction."""
        tool_log = getattr(self, '_last_tool_log', None)
        if not tool_log:
            self.console.print('[dim]No tool calls recorded. Run "ask" or "marcus" first.[/dim]')
            return

        table = Table(title='Last Marcus Tool Calls', border_style=self.colors['primary'])
        table.add_column('#', style=self.colors['dim'], width=3)
        table.add_column('Type', style=self.colors['accent'], width=10)
        table.add_column('Name', style=f'bold {self.colors["primary"]}')
        table.add_column('Details')

        for i, entry in enumerate(tool_log, 1):
            if entry['role'] == 'tool call':
                name = entry.get('name', 'tool')
                # Try to show input summary
                detail = ''
                try:
                    data = json.loads(entry['content']) if isinstance(entry['content'], str) else entry['content']
                    if isinstance(data, dict):
                        inp = data.get('input', data.get('arguments', data))
                        detail = json.dumps(inp, default=str)
                        if len(detail) > 120:
                            detail = detail[:120] + '...'
                except Exception:
                    detail = entry['content'][:120] if entry['content'] else ''
                table.add_row(str(i), 'call', name, detail)
            elif entry['role'] == 'tool response':
                name = entry.get('name', '')
                summary = entry.get('summary', '')
                detail = summary if summary else ''
                if not detail:
                    detail = entry['content'][:120] + '...' if len(entry['content']) > 120 else entry['content']
                table.add_row(str(i), 'response', name, detail)

        self.console.print(table)
        self.console.print(f'[dim]Use "set verbose on" to see full details inline during Marcus queries.[/dim]')

    def _cmd_use(self, args):
        """Select a tool/capability or switch engagement -- context-aware."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        if not args:
            self._cmd_run([])  # show available tools
            return

        name = args[0]

        # If it's a number, resolve from capability list or account list
        if name.isdigit():
            idx = int(name) - 1
            # Try capability list first (from "capabilities" command)
            if hasattr(self, '_capability_list') and self._capability_list and 0 <= idx < len(self._capability_list):
                self._cmd_use([self._capability_list[idx]])
                return
            # Then account list (from "accounts" command)
            if hasattr(self, '_account_list') and self._account_list and 0 <= idx < len(self._account_list):
                self._cmd_switch([name])
                return
            self.console.print(f'[dim]Run "capabilities" or "accounts" first, then "use <#>".[/dim]')
            return

        # If it looks like an email, switch engagement
        if '@' in name:
            self._cmd_switch([name])
            return

        tool_name = name.lower()

        # Check named aliases first
        if tool_name in TOOL_ALIASES:
            alias = TOOL_ALIASES[tool_name]
            self.context.active_tool = tool_name
            self.context.active_tool_config = dict(alias.get('default_config', {}))
            self.console.print(f'[info]Using {tool_name} -- {alias["description"]}[/info]')
            self.console.print(f'[dim]Target type: {alias["target_type"]}. Use "show targets" to see valid targets.[/dim]')
            return

        # Try resolving as a backend capability name (any of the 141 capabilities)
        cap_info = self._resolve_backend_capability(tool_name)
        if cap_info:
            self.context.active_tool = tool_name
            self.context.active_tool_config = {}
            target_type = cap_info.get('target', 'asset')
            if isinstance(target_type, list):
                target_type = target_type[0] if target_type else 'asset'
            desc = cap_info.get('description', '')[:60]
            self.console.print(f'[info]Using {tool_name} -- {desc}[/info]')
            self.console.print(f'[dim]Target type: {target_type}. Use "show targets" to see valid targets.[/dim]')
            # Dynamically add to TOOL_ALIASES for this session so execute/run work
            TOOL_ALIASES[tool_name] = {
                'capability': tool_name,
                'agent': None,
                'target_type': target_type,
                'description': desc,
            }
            return

        available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
        self.console.print(f'[error]Unknown: {tool_name}. Named tools: {available}[/error]')
        self.console.print(f'[dim]Or use any backend capability name -- run "capabilities" to see all 141.[/dim]')

    def _resolve_backend_capability(self, name):
        """Check if a name matches a backend capability. Returns cap dict or None."""
        if not hasattr(self, '_capabilities_cache'):
            try:
                result = self.sdk.capabilities.list(name='')
                if isinstance(result, list):
                    self._capabilities_cache = {c.get('name', '').lower(): c for c in result}
                elif isinstance(result, dict):
                    caps = result.get('capabilities', result.get('data', []))
                    self._capabilities_cache = {c.get('name', '').lower(): c for c in caps}
                else:
                    self._capabilities_cache = {}
            except Exception:
                self._capabilities_cache = {}
        return self._capabilities_cache.get(name.lower())

    def _cmd_options(self, args):
        """Show current tool options -- Metasploit-style."""
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
        """Execute the active tool against the target -- Metasploit-style."""
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
        """Clear tool selection -- Metasploit-style."""
        if self.context.active_tool:
            self.console.print(f'[dim]Deselected {self.context.active_tool}[/dim]')
            self.context.clear_tool()
        else:
            self.console.print('[dim]Nothing to go back from.[/dim]')
