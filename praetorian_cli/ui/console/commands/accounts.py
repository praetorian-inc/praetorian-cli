"""Account/engagement commands: accounts/switch/home. Mixed into GuardConsole."""

import json

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class AccountCommands:
    """Account and engagement console commands. Mixed into GuardConsole."""

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
                    # I'm listed as member -> this is an account I can access
                    authorized.append(acct)
                elif acct.get('name') == (login or current):
                    # I own this account -> this person collaborates with me
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
                    is_active = '->' if account_email == self.context.account else ''
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
        """Return to your own account -- unimpersonate."""
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
        """Create a new customer -- console wrapper."""
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
        """Create engagement vault -- routes through Marcus."""
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
        """Full onboarding -- routes through Marcus."""
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
