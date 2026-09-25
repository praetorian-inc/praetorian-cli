"""Tests for multi-account agent loading and grouping."""
from datetime import datetime
from unittest.mock import MagicMock, patch
from praetorian_cli.sdk.model.aegis import Agent


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

    def test_load_agents_rebinds_selected_agent_with_matching_account(self):
        """A selected agent with a duplicate ID should refresh within its account."""
        from praetorian_cli.ui.aegis.menu import AegisMenu

        sdk = MagicMock()
        sdk.keychain.account = None
        sdk.get_current_user.return_value = ('op@p.com', 'op')

        acme = _make_account_info('acme@p.com', 'Acme', 'ACTIVE')
        beta = _make_account_info('beta@p.com', 'Beta', 'ACTIVE')
        menu = AegisMenu(sdk)
        menu.multi_account_mode = True
        menu.selected_accounts = [acme, beta]

        stale_beta_agent = _make_agent('old-beta', client_id='C.same', has_tunnel=False)
        stale_beta_agent._account_info = beta
        fresh_acme_agent = _make_agent('acme-host', client_id='C.same', has_tunnel=False)
        fresh_beta_agent = _make_agent('beta-host', client_id='C.same', has_tunnel=True)
        menu.selected_agent = stale_beta_agent

        with patch('praetorian_cli.ui.aegis.menu.load_agents_for_accounts') as mock_load:
            mock_load.return_value = ([
                (fresh_acme_agent, acme),
                (fresh_beta_agent, beta),
            ], [])
            menu.load_agents()

        assert menu.selected_agent is fresh_beta_agent
        assert menu.selected_agent.has_tunnel is True


class TestMultiAccountAgentTable:
    def test_endpoint_without_heartbeat_renders_as_offline(self):
        """Endpoint rows without heartbeat metadata should not crash grouping."""
        from praetorian_cli.ui.aegis.utils import compute_agent_groups

        endpoint = Agent.from_endpoint_dict({
            'endpointId': 'endpoint-1',
            'kind': 'aegis',
            'hostname': 'sensor-1',
        })

        groups = compute_agent_groups([endpoint], datetime.now().timestamp())

        assert groups['active_tunnel'] == []
        assert groups['online'] == []
        assert groups['offline'][0][1] is endpoint


