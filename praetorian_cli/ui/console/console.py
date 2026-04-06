#!/usr/bin/env python3
"""Guard Interactive Console -- operator-focused engagement interface."""

import os
import shlex
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from rich.console import Console
from rich.table import Table
from rich.text import Text

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.ui.aegis.theme import (
    AEGIS_COLORS, AEGIS_RICH_THEME,
    PRIMARY_RED, COMPLEMENTARY_GOLD, SECONDARY_TEXT,
)
from praetorian_cli.ui.console.context import EngagementContext
from praetorian_cli.ui.console.renderer import RendererMixin
from praetorian_cli.ui.console.commands import (
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
)


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
    'critfinder', 'research', 'hunt',
    'aegis',
    'configure', 'login',
    'help', 'history', 'clear', 'quit', 'exit',
]


class GuardConsole(
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
    RendererMixin,
):
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
        """Build a colored prompt -- Praetorian red for guard, gold for subshells."""
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
        if self.context.account:
            # Show short account label (strip chariot+/guard+ prefix and @praetorian.com suffix)
            acct = self.context.account
            for prefix in ('chariot+', 'guard+'):
                if acct.startswith(prefix):
                    acct = acct[len(prefix):]
                    break
            acct = acct.replace('@praetorian.com', '')
            return HTML(
                f'<style fg="{PRIMARY_RED}" bg="">guard</style>'
                f' <style fg="{COMPLEMENTARY_GOLD}" bg="">[{acct}]</style>'
                f' <style fg="{PRIMARY_RED}" bg="">&gt;</style> '
            )
        return HTML(f'<style fg="{PRIMARY_RED}" bg="">guard &gt;</style> ')

    def _show_banner(self):
        ascii_art = (
            "                                    \u2588\u2588 \u2588\u2588\u2588\u2588                     \u2588\u2588\u2588\u2588 \u2588\u2588\n"
            "                                 \u2588\u2588 \u2588\u2588\u2588                             \u2588\u2588\u2588 \u2588\u2588\n"
            "                                 \u2588\u2588\u2588                                   \u2588\u2588\u2588\n"
            "                              \u2588  \u2588\u2588\u2588\u2588\u2588                               \u2588\u2588\u2588\u2588\u2588  \u2588\n"
            "                             \u2588\u2588\u2588\u2588                                         \u2588\u2588\u2588\u2588\n"
            "                              \u2588\u2588\u2588\u2588\u2588                                     \u2588\u2588\u2588\u2588\u2588\n"
            "                           \u2588\u2588\u2588\u2588\u2588                                           \u2588\u2588\u2588\u2588\u2588\n"
            "                           \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588                                     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                             \u2588\u2588\u2588                                           \u2588\u2588\u2588\n"
            "                         \u2588\u2588\u2588 \u2588  \u2588\u2588\u2588                                     \u2588\u2588\u2588\u2588 \u2588 \u2588\u2588\u2588\n"
            "                          \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588                                       \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                           \u2588\u2588\u2588\u2588\u2588   \u2588                                    \u2588  \u2588\u2588\u2588\u2588\u2588\n"
            "                              \u2588 \u2588\u2588\u2588                                     \u2588\u2588\u2588 \u2588\n"
            "                          \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588                                     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                           \u2588\u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588                               \u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                                \u2588\u2588 \u2588\u2588\u2588  \u2588\u2588                        \u2588  \u2588\u2588\u2588 \u2588\u2588\n"
            "                                 \u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588  \u2588\u2588               \u2588\u2588  \u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\n"
            "                            \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588             \u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                               \u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588           \u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\n"
            "                                   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588           \u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                                \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588           \u2588\u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                                        \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                                      \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588     \u2588\u2588\u2588\u2588\u2588     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            "                                        \u2588\u2588        \u2588\u2588\u2588 \u2588\u2588\u2588\u2588       \u2588\u2588\n"
            "                                                \u2588\u2588       \u2588\u2588"
        )
        self.console.print(f'[{PRIMARY_RED}]{ascii_art}[/{PRIMARY_RED}]')
        self.console.print()

        title = Text()
        title.append('Guard Console', style=f'bold {PRIMARY_RED}')
        title.append(' -- ', style=self.colors['dim'])
        title.append('Praetorian Offensive Security Platform', style=f'{COMPLEMENTARY_GOLD}')
        self.console.print(title, justify='center')
        self.console.print()

        ctx_line = Text()
        ctx_line.append(f'Context: {self.context.summary()}', style=self.colors['dim'])
        self.console.print(ctx_line, justify='center')
        self.console.print(f'[dim]Type "help" for commands.[/dim]\n', justify='center')

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
            'critfinder': self._cmd_critfinder,
            'research': self._cmd_research,
            'hunt': self._cmd_hunt,
            'aegis': self._cmd_aegis,
            'configure': self._cmd_configure,
            'login': self._cmd_configure,
            'help': self._cmd_help,
            'clear': self._cmd_clear,
            'quit': self._cmd_quit_or_back,
            'exit': self._cmd_quit_or_back,
        }

        # Direct tool name aliases: "brutus <key>" -> "run brutus <key>"
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

    # -- Aegis ---------------------------------------------------------------

    def _cmd_aegis(self, args):
        try:
            from praetorian_cli.ui.aegis.menu import AegisMenu
            menu = AegisMenu(self.sdk)
            menu.run()
        except ImportError:
            self.console.print('[error]Aegis module not available[/error]')
        except Exception as e:
            self.console.print(f'[error]Aegis error: {e}[/error]')

    # -- Utility commands ----------------------------------------------------

    def _cmd_help(self, args):
        help_table = Table(title='Guard Console Commands', border_style=self.colors['primary'])
        help_table.add_column('Command', style=f'bold {self.colors["primary"]}', min_width=25)
        help_table.add_column('Description')

        help_table.add_row('[section]Context[/section]', '')
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
        help_table.add_row('[section]Search & Recon[/section]', '')
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
        help_table.add_row('[section]Operations[/section]', '')
        help_table.add_row('scan <asset> [cap]', 'Schedule a scan job')
        help_table.add_row('tag <risk> <tag...>', 'Tag a risk')

        help_table.add_row('', '')
        help_table.add_row('[section]Security Tools (Metasploit-style)[/section]', '')
        help_table.add_row('use <tool>', 'Select a tool (brutus, nuclei, julius, etc.)')
        help_table.add_row('show targets', 'Show valid targets for active tool')
        help_table.add_row('set target <key|#>', 'Set target (key or number from list)')
        help_table.add_row('options', 'Show current tool options')
        help_table.add_row('execute / exploit', 'Run the active tool against the target')
        help_table.add_row('back', 'Deselect current tool')
        help_table.add_row('', '')
        help_table.add_row('[section]Agents & Capabilities[/section]', '')
        help_table.add_row('asset-analyzer <key>', 'Deep-dive recon & risk mapping')
        help_table.add_row('brutus <port_key>', 'Credential attacks (SSH, RDP, FTP, SMB)')
        help_table.add_row('julius <port_key>', 'LLM/AI service fingerprinting')
        help_table.add_row('augustus <webpage_key>', 'LLM jailbreak & injection attacks')
        help_table.add_row('aurelius <asset_key>', 'Cloud infrastructure discovery')
        help_table.add_row('trajan <asset_key>', 'CI/CD pipeline security scanning')
        help_table.add_row('priscus <risk_key>', 'Remediation retesting')
        help_table.add_row('seneca <risk_key>', 'CVE research & exploit intelligence')
        help_table.add_row('titus <repo_key>', 'Secret scanning & credential leak detection')
        help_table.add_row('nuclei <asset_key>', 'Vulnerability scanner')
        help_table.add_row('portscan <asset_key>', 'Port scanning')
        help_table.add_row('capabilities [name]', 'List all backend capabilities')
        help_table.add_row('install <tool|all>', 'Install binary from GitHub')
        help_table.add_row('installed', 'List locally installed binaries')

        help_table.add_row('', '')
        help_table.add_row('[section]Evidence & Reports[/section]', '')
        help_table.add_row('evidence <risk_key>', 'Hydrated evidence for a risk')
        help_table.add_row('report generate [opts]', 'Generate engagement report')
        help_table.add_row('report validate [opts]', 'Validate report requirements')

        help_table.add_row('', '')
        help_table.add_row('[section]CritFinder Research[/section]', '')
        help_table.add_row('critfinder [target]', 'Run adversarial vuln research pipeline')
        help_table.add_row('critfinder --depth 3', 'Iterative deep hunt (multiple cycles)')
        help_table.add_row('critfinder --novel', '0day hunting mode')
        help_table.add_row('critfinder --mode knowledge <topic>', 'Knowledge research mode')
        help_table.add_row('research / hunt', 'Aliases for critfinder')

        help_table.add_row('', '')
        help_table.add_row('[section]Marcus Aurelius[/section]', '')
        help_table.add_row('ask "<question>"', 'One-shot query to Marcus')
        help_table.add_row('marcus', 'Enter multi-turn conversation')
        help_table.add_row('marcus read <path>', 'Read & analyze a file (vault, proofs, etc.)')
        help_table.add_row('marcus ingest <path>', 'Read file & auto-create seeds/risks')
        help_table.add_row('marcus do "<instruction>"', 'Direct instruction (full agent access)')
        help_table.add_row('marcus research [target]', 'Run CritFinder via Marcus')

        help_table.add_row('', '')
        help_table.add_row('[section]Other[/section]', '')
        help_table.add_row('aegis', 'Open Aegis agent manager')
        help_table.add_row('clear', 'Clear screen')
        help_table.add_row('help', 'Show this help')
        help_table.add_row('quit', 'Exit console')

        self.console.print(help_table)

    def _cmd_configure(self, args):
        """Configure API keys -- runs inline in the console."""
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


def run_console(sdk: Chariot, account: Optional[str] = None):
    """Entry point for the interactive console."""
    console = GuardConsole(sdk, account=account)
    console.run()
