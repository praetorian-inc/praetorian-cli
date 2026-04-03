"""Tests for multi-account agent and schedule table rendering."""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from rich.console import Console
from praetorian_cli.ui.aegis.theme import AEGIS_RICH_THEME, AEGIS_COLORS


def _make_agent(hostname='host1', client_id=None, is_online=True, has_tunnel=True, last_seen=None):
    agent = MagicMock()
    agent.hostname = hostname
    agent.client_id = client_id or f'C.{hostname}'
    agent.os = 'linux'
    agent.os_version = '22.04'
    agent.is_online = is_online
    agent.has_tunnel = has_tunnel
    agent.last_seen_at = last_seen or 1709000000
    agent.network_interfaces = []
    agent.health_check = MagicMock()
    agent.health_check.cloudflared_status = MagicMock()
    agent.health_check.cloudflared_status.hostname = 'tunnel.example.com' if has_tunnel else None
    return agent


def _make_account_info(email, name='Test Corp', status='ACTIVE'):
    return {
        'account_email': email,
        'display_name': name,
        'status': status,
        'account_type': 'MANAGED',
        'agent_count': 1,
    }


class TestMultiAccountAgentLoading:
    def test_load_agents_multi_account_mode(self):
        """In multi-account mode, load_agents should aggregate across accounts."""
        from praetorian_cli.ui.aegis.menu import AegisMenu

        sdk = MagicMock()
        sdk.keychain.account = None
        sdk.get_current_user.return_value = ('op@p.com', 'op')

        menu = AegisMenu(sdk)
        menu.multi_account_mode = True
        menu.selected_accounts = [
            _make_account_info('acme@p.com', 'Acme', 'ACTIVE'),
            _make_account_info('beta@p.com', 'Beta', 'COMPLETED'),
        ]

        agent1 = _make_agent('srv1')
        agent2 = _make_agent('srv2')
        agent3 = _make_agent('srv3')

        with patch('praetorian_cli.ui.aegis.menu.load_agents_for_accounts') as mock_load:
            mock_load.return_value = ([
                (agent1, menu.selected_accounts[0]),
                (agent2, menu.selected_accounts[0]),
                (agent3, menu.selected_accounts[1]),
            ], [])
            menu.load_agents()

        assert len(menu.agents) == 3
        assert len(menu.agent_account_map) == 3
        assert menu.agent_account_map[agent1.client_id]['status'] == 'ACTIVE'
        assert menu.agent_account_map[agent3.client_id]['status'] == 'COMPLETED'


class TestMultiAccountAgentTable:
    def test_agent_table_has_account_columns(self):
        """In multi-account mode, agent table should show ACCOUNT and ACCT STATUS columns."""
        from praetorian_cli.ui.aegis.menu import AegisMenu

        sdk = MagicMock()
        sdk.keychain.account = None
        sdk.get_current_user.return_value = ('op@p.com', 'op')

        menu = AegisMenu(sdk)
        menu.multi_account_mode = True
        menu.selected_accounts = [
            _make_account_info('chariot+cushwake@praetorian.com', 'Cushman & Wakefield', 'ACTIVE'),
        ]

        agent = _make_agent('dc01.internal')
        menu.agents = [agent]
        menu.displayed_agents = [agent]
        menu.agent_account_map = {
            agent.client_id: menu.selected_accounts[0],
        }

        output = StringIO()
        menu.console = Console(file=output, force_terminal=True, width=150, theme=AEGIS_RICH_THEME)
        menu.show_agents_list()
        text = output.getvalue()

        assert 'ACCOUNT' in text
        assert 'ACCT STATUS' in text
        assert 'dc01.internal' in text
        # Display name truncated to 19 chars: "Cushman & Wakefie..."
        assert 'Cushman & Wakefie' in text


class TestMultiAccountScheduleTable:
    def test_schedule_table_has_account_columns(self):
        """In multi-account mode, schedule table should show account columns."""
        from praetorian_cli.ui.aegis.commands.schedule import list_schedules

        menu = MagicMock()
        menu.multi_account_mode = True
        menu.colors = AEGIS_COLORS
        menu.selected_accounts = [
            _make_account_info('acme@praetorian.com', 'Acme', 'ACTIVE'),
        ]
        menu.agent_lookup = {}

        output = StringIO()
        menu.console = Console(file=output, force_terminal=True, width=200, theme=AEGIS_RICH_THEME)

        with patch('praetorian_cli.ui.aegis.commands.schedule.load_schedules_for_accounts') as mock_load:
            mock_load.return_value = ([
                ({
                    'scheduleId': 's1',
                    'capabilityName': 'windows-smb-snaffler',
                    'targetKey': '#asset#srv1#srv1',
                    'status': 'active',
                    'weeklySchedule': {},
                    'nextExecution': '',
                    'clientId': 'C.srv1',
                }, menu.selected_accounts[0]),
            ], [])
            list_schedules(menu)

        text = output.getvalue()
        assert 'ACCOUNT' in text
        assert 'ACCT STATUS' in text
