"""Interactive account selection table for multi-account aegis mode.

Renders a Rich table with checkbox column, account status, name, address, and type.
First two rows are special: "Select all active" and "Select all regardless of status".
"""

import os
from typing import List, Set
from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL

from praetorian_cli.sdk.entities.account_discovery import truncate_email


# Row indices for special actions
ROW_SELECT_ALL = 0
ROW_SELECT_ALL_ACTIVE = 1
SPECIAL_ROW_COUNT = 2


class AccountSelector:
    """Manages account selection state and table rendering."""

    def __init__(self, accounts: List[dict], colors: dict):
        self.accounts = accounts
        self.colors = colors
        self.selected_indices: Set[int] = set()  # indices into self.accounts
        self.cursor = 0  # current row in display (0-based, includes special rows)

    def build_table(self) -> Table:
        """Build the Rich table for display."""
        table = Table(
            show_header=True,
            header_style=f"{self.colors['dim']}",
            border_style=self.colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False,
        )

        table.add_column("", width=3, no_wrap=True)           # checkbox
        table.add_column("ACCOUNT", min_width=20, no_wrap=False)
        table.add_column("ADDRESS", min_width=20, no_wrap=True)
        table.add_column("STATUS", width=10, no_wrap=True)
        table.add_column("TYPE", width=10, no_wrap=True)
        table.add_column("ONLINE", width=6, justify="right", no_wrap=True)
        table.add_column("ALL", width=6, justify="right", no_wrap=True)

        empty = Text("", style=self.colors['dim'])

        # Special row 1: Select all
        check_all = self._checkbox_char(self._all_selected())
        is_cursor_all = (self.cursor == ROW_SELECT_ALL)
        table.add_row(
            Text(check_all, style=f"bold {self.colors['accent']}"),
            Text("Select all", style="bold white" if is_cursor_all else f"bold {self.colors['primary']}"),
            empty, empty, empty, empty, empty,
        )

        # Special row 2: Select all active
        check_all_active = self._checkbox_char(self._all_active_selected())
        is_cursor_active = (self.cursor == ROW_SELECT_ALL_ACTIVE)
        table.add_row(
            Text(check_all_active, style=f"bold {self.colors['accent']}"),
            Text("Select all active", style="bold white" if is_cursor_active else f"bold {self.colors['primary']}"),
            empty, empty, empty, empty, empty,
        )

        # Account rows
        for i, acct in enumerate(self.accounts):
            checked = i in self.selected_indices
            checkbox = self._checkbox_char(checked)
            is_cursor = (self.cursor == SPECIAL_ROW_COUNT + i)
            agent_count = str(acct.get('agent_count', 0))
            online_count = acct.get('online_count', 0)
            online_str = str(online_count)
            status = acct.get('status', 'UNKNOWN')
            acct_type = acct.get('account_type', 'UNKNOWN')

            table.add_row(
                Text(checkbox, style=f"{self.colors['accent']}" if checked else self.colors['dim']),
                Text(acct.get('display_name', ''), style="bold white" if is_cursor else "white"),
                Text(truncate_email(acct.get('account_email', ''), 19), style=self.colors['dim']),
                Text(status, style=self._status_style(status)),
                Text(acct_type, style=self.colors['dim']),
                Text(online_str, style=self.colors['success'] if online_count > 0 else self.colors['dim']),
                Text(agent_count, style=self.colors['dim']),
            )

        return table

    def toggle(self, display_row: int) -> None:
        """Toggle selection for a display row. Handles special rows."""
        if display_row == ROW_SELECT_ALL_ACTIVE:
            if self._all_active_selected():
                for i, acct in enumerate(self.accounts):
                    if acct.get('status', '').upper() == 'ACTIVE':
                        self.selected_indices.discard(i)
            else:
                self.select_all_active()
        elif display_row == ROW_SELECT_ALL:
            if self._all_selected():
                self.selected_indices.clear()
            else:
                self.select_all()
        else:
            account_idx = display_row - SPECIAL_ROW_COUNT
            if 0 <= account_idx < len(self.accounts):
                if account_idx in self.selected_indices:
                    self.selected_indices.discard(account_idx)
                else:
                    self.selected_indices.add(account_idx)

    def select_all_active(self) -> None:
        """Select all accounts with ACTIVE status."""
        for i, acct in enumerate(self.accounts):
            if acct.get('status', '').upper() == 'ACTIVE':
                self.selected_indices.add(i)

    def select_all(self) -> None:
        """Select all accounts regardless of status."""
        self.selected_indices = set(range(len(self.accounts)))

    def get_selected_accounts(self) -> List[dict]:
        """Return the list of selected account info dicts."""
        return [self.accounts[i] for i in sorted(self.selected_indices)]

    def total_rows(self) -> int:
        """Total display rows including special rows."""
        return SPECIAL_ROW_COUNT + len(self.accounts)

    def _all_active_selected(self) -> bool:
        active_indices = {i for i, a in enumerate(self.accounts) if a.get('status', '').upper() == 'ACTIVE'}
        return bool(active_indices) and active_indices.issubset(self.selected_indices)

    def _all_selected(self) -> bool:
        return len(self.selected_indices) == len(self.accounts) and len(self.accounts) > 0

    def _checkbox_char(self, checked: bool) -> str:
        return "[x]" if checked else "[ ]"

    def _status_style(self, status: str) -> str:
        s = status.upper()
        if s == 'ACTIVE':
            return self.colors['success']
        elif s == 'COMPLETED':
            return self.colors['dim']
        elif s == 'PAUSED':
            return self.colors['warning']
        return self.colors['dim']


def run_account_selector(accounts: List[dict], colors: dict, console) -> List[dict]:
    """Run the interactive account selector and return selected accounts.

    Renders a table with arrow key navigation and spacebar toggling.
    Enter confirms selection. 'q' or Escape cancels (returns []).

    Uses prompt_toolkit Application for keyboard input (no readchar dependency).

    Args:
        accounts: List of account info dicts from discover_aegis_accounts
        colors: Aegis color theme dict
        console: Rich Console instance

    Returns:
        List of selected account info dicts, or [] if cancelled.
    """
    from io import StringIO
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    if not accounts:
        console.print("  No accounts with aegis agents found.")
        return []

    selector = AccountSelector(accounts, colors)
    selector.cursor = 0
    result_holder = []  # mutable container for result from key handler

    kb = KeyBindings()

    @kb.add('up')
    def _(event):
        selector.cursor = max(0, selector.cursor - 1)

    @kb.add('down')
    def _(event):
        selector.cursor = min(selector.total_rows() - 1, selector.cursor + 1)

    @kb.add(' ')
    def _(event):
        selector.toggle(selector.cursor)

    @kb.add('enter')
    def _(event):
        selected = selector.get_selected_accounts()
        if selected:
            result_holder.clear()
            result_holder.extend(selected)
            event.app.exit()

    @kb.add('q')
    @kb.add('escape')
    def _(event):
        result_holder.clear()
        event.app.exit()

    @kb.add('c-c')
    def _(event):
        result_holder.clear()
        event.app.exit()

    def _get_display_text():
        """Render the selector as ANSI text for prompt_toolkit."""
        output = StringIO()
        from rich.console import Console as _Console
        from rich.theme import Theme
        from .theme import AEGIS_RICH_THEME
        render_console = _Console(
            file=output, force_terminal=True,
            width=console.width, theme=AEGIS_RICH_THEME,
        )
        render_console.print(f"\n[bold {colors['primary']}]Aegis Multi-Account Selection[/bold {colors['primary']}]")
        render_console.print(f"  [{colors['dim']}]↑/↓ navigate  SPACE toggle  ENTER confirm  q quit[/{colors['dim']}]\n")
        table = selector.build_table()
        render_console.print(table)
        render_console.print()
        selected_count = len(selector.selected_indices)
        render_console.print(f"  [{colors['dim']}]{selected_count} account(s) selected — press ENTER to continue[/{colors['dim']}]")
        return ANSI(output.getvalue())

    layout = Layout(Window(content=FormattedTextControl(_get_display_text)))
    app = Application(layout=layout, key_bindings=kb, full_screen=True)
    app.run()

    return result_holder
