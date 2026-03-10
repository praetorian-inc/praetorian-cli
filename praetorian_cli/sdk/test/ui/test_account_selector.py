"""Tests for the multi-account selection UI."""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from rich.console import Console


def _make_account_info(email, name='Test Corp', status='ACTIVE', acct_type='MANAGED', agent_count=3):
    return {
        'account_email': email,
        'display_name': name,
        'status': status,
        'account_type': acct_type,
        'agent_count': agent_count,
    }


class TestAccountSelector:
    def test_render_table_has_correct_columns(self):
        from praetorian_cli.ui.aegis.account_selector import AccountSelector
        from praetorian_cli.ui.aegis.theme import AEGIS_COLORS

        accounts = [
            _make_account_info('acme@p.com', 'Acme Corp', 'ACTIVE', 'MANAGED'),
            _make_account_info('beta@p.com', 'Beta Inc', 'COMPLETED', 'PILOT'),
        ]
        selector = AccountSelector(accounts, AEGIS_COLORS)
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        table = selector.build_table()
        console.print(table)
        text = output.getvalue()

        assert 'ACCOUNT' in text
        assert 'ADDRESS' in text
        assert 'STATUS' in text
        assert 'TYPE' in text
        assert 'AGENTS' in text

    def test_special_rows_present(self):
        from praetorian_cli.ui.aegis.account_selector import AccountSelector
        from praetorian_cli.ui.aegis.theme import AEGIS_COLORS

        accounts = [
            _make_account_info('acme@p.com', 'Acme Corp', 'ACTIVE', 'MANAGED'),
        ]
        selector = AccountSelector(accounts, AEGIS_COLORS)
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        table = selector.build_table()
        console.print(table)
        text = output.getvalue()

        assert 'Select all active' in text
        assert 'Select all' in text

    def test_toggle_account(self):
        from praetorian_cli.ui.aegis.account_selector import AccountSelector, SPECIAL_ROW_COUNT
        from praetorian_cli.ui.aegis.theme import AEGIS_COLORS

        accounts = [
            _make_account_info('acme@p.com'),
            _make_account_info('beta@p.com'),
        ]
        selector = AccountSelector(accounts, AEGIS_COLORS)

        assert len(selector.selected_indices) == 0

        # Toggle first real account (row index = SPECIAL_ROW_COUNT + 0)
        selector.toggle(SPECIAL_ROW_COUNT)
        assert 0 in selector.selected_indices

        selector.toggle(SPECIAL_ROW_COUNT)
        assert 0 not in selector.selected_indices

    def test_select_all_active(self):
        from praetorian_cli.ui.aegis.account_selector import AccountSelector
        from praetorian_cli.ui.aegis.theme import AEGIS_COLORS

        accounts = [
            _make_account_info('acme@p.com', status='ACTIVE'),
            _make_account_info('beta@p.com', status='COMPLETED'),
            _make_account_info('gamma@p.com', status='ACTIVE'),
        ]
        selector = AccountSelector(accounts, AEGIS_COLORS)
        selector.select_all_active()

        selected = selector.get_selected_accounts()
        assert len(selected) == 2
        emails = {a['account_email'] for a in selected}
        assert emails == {'acme@p.com', 'gamma@p.com'}

    def test_select_all(self):
        from praetorian_cli.ui.aegis.account_selector import AccountSelector
        from praetorian_cli.ui.aegis.theme import AEGIS_COLORS

        accounts = [
            _make_account_info('acme@p.com', status='ACTIVE'),
            _make_account_info('beta@p.com', status='COMPLETED'),
        ]
        selector = AccountSelector(accounts, AEGIS_COLORS)
        selector.select_all()

        selected = selector.get_selected_accounts()
        assert len(selected) == 2


class TestNoAccountDetection:
    @patch('praetorian_cli.sdk.entities.account_discovery.discover_aegis_accounts', return_value=[])
    def test_keychain_account_none_triggers_multi_account(self, mock_discover):
        from praetorian_cli.ui.aegis.menu import run_aegis_menu

        sdk = MagicMock()
        sdk.keychain.account = None

        run_aegis_menu(sdk)

        mock_discover.assert_called_once()

    @patch('praetorian_cli.sdk.entities.account_discovery.discover_aegis_accounts')
    def test_keychain_account_set_skips_multi_account(self, mock_discover):
        from praetorian_cli.ui.aegis.menu import run_aegis_menu

        sdk = MagicMock()
        sdk.keychain.account = 'client@praetorian.com'

        with patch('praetorian_cli.ui.aegis.menu.AegisMenu') as mock_menu_cls:
            mock_menu_instance = MagicMock()
            mock_menu_cls.return_value = mock_menu_instance
            run_aegis_menu(sdk)

        mock_discover.assert_not_called()
        mock_menu_cls.assert_called_once_with(sdk)
        mock_menu_instance.run.assert_called_once()
