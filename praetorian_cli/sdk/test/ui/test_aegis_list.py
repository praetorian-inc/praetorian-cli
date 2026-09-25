from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.ui.aegis.commands.list import handle_list
from praetorian_cli.ui.aegis.commands.set import handle_set
from praetorian_cli.ui.aegis.menu import AegisMenu

pytestmark = pytest.mark.tui


def test_list_renders_persisted_v2_tunnel_state():
    class Search:
        def by_key_prefix(self, key):
            if key == '#endpoint#':
                return [], None
            if key == '#endpointaegistunnelstate#':
                return [{
                    'endpointId': 'endpoint-1',
                    'cloudflaredStatus': {
                        'status': 'configured',
                        'hostname': 'sensor.example.com',
                        'tunnel_name': 'sensor-tunnel',
                    },
                }], None
            if key == '#endpointaegisstatus#':
                return [], None
            raise AssertionError(f'unexpected key: {key}')

    class API:
        search = Search()

        def get(self, path, params=None):
            if path == '/agent/enhanced':
                return []
            if path == 'endpoint/list':
                return {'endpoints': [{
                    'endpointId': 'endpoint-1',
                    'kind': 'aegis',
                    'lifecycleState': 'Active',
                    'lastSeenAt': datetime.now(timezone.utc).isoformat(),
                    'profile': {'hostname': 'sensor-1', 'os': 'linux'},
                }]}
            raise AssertionError(f'unexpected path: {path}')

    sdk = SimpleNamespace(
        aegis=Aegis(API()),
        get_current_user=lambda: ('user@example.com', 'user'),
    )
    menu = AegisMenu(sdk)
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_list(menu, [])

    output = menu.console.export_text()
    assert 'sensor-1' in output
    assert 'active' in output


def test_list_all_renders_offline_v2_endpoint_from_durable_identity():
    class Search:
        def by_key_prefix(self, key):
            if key == '#endpointaegistunnelstate#':
                return [{
                    'endpointId': 'endpoint-offline',
                    'cloudflaredStatus': {
                        'status': 'configured',
                        'hostname': 'sensor.example.com',
                    },
                }], None
            if key in ('#endpoint#', '#endpointaegisstatus#'):
                return [], None
            raise AssertionError(f'unexpected key: {key}')

    class API:
        search = Search()

        def get(self, path, params=None):
            if path == '/agent/enhanced':
                return []
            if path == 'endpoint/list':
                return {'endpoints': [{
                    'endpointId': 'endpoint-offline',
                    'kind': 'aegis',
                    'lifecycleState': 'Active',
                    'connectionState': 'not_connected',
                    'profile': {
                        'hostname': 'offline-sensor',
                        'os': 'linux',
                    },
                }]}
            if path == 'endpoint':
                return []
            raise AssertionError(f'unexpected path: {path}')

    sdk = SimpleNamespace(
        aegis=Aegis(API()),
        get_current_user=lambda: ('user@example.com', 'user'),
    )
    menu = AegisMenu(sdk)
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_list(menu, ['--all'])

    output = menu.console.export_text()
    assert 'offline-sensor' in output
    assert 'v2' in output
    assert 'linux' in output
    assert 'offline' in output
    assert 'active' in output


class InventoryAPI:
    def __init__(self):
        self.legacy = []
        self.endpoints = []
        self.legacy_error = None
        self.endpoint_error = None
        self.search = self

    def get(self, path, params=None):
        if path == '/agent/enhanced':
            if self.legacy_error:
                raise self.legacy_error
            return self.legacy
        if path in ('endpoint/list', 'endpoint'):
            if self.endpoint_error:
                raise self.endpoint_error
            return {'endpoints': self.endpoints}
        raise AssertionError(f'unexpected path: {path}')

    def by_key_prefix(self, key):
        if self.endpoint_error:
            raise self.endpoint_error
        return [], None


@pytest.fixture
def inventory_menu():
    api = InventoryAPI()
    api.endpoints = [{
        'endpointId': 'endpoint-healthy',
        'kind': 'aegis',
        'lifecycleState': 'Active',
        'lastSeenAt': datetime.now(timezone.utc).isoformat(),
        'profile': {'hostname': 'healthy-sensor', 'os': 'linux'},
    }]
    sdk = SimpleNamespace(
        aegis=Aegis(api),
        get_current_user=lambda: ('user@example.com', 'user'),
    )
    menu = AegisMenu(sdk)
    menu.verbose = False
    menu.console = Console(file=StringIO(), record=True, force_terminal=False, width=240)
    return menu, api


@pytest.mark.parametrize('failed_source', ['legacy', 'v2'])
def test_partial_inventory_keeps_healthy_agents_selectable(inventory_menu, failed_source):
    menu, api = inventory_menu
    failure = RuntimeError('[red]inventory failure[/red]')
    if failed_source == 'legacy':
        api.legacy_error = failure
        expected_id = 'endpoint-healthy'
    else:
        api.endpoint_error = failure
        api.legacy = [{
            'client_id': 'legacy-healthy',
            'hostname': 'healthy-legacy',
            'os': 'linux',
            'last_seen_at': datetime.now(timezone.utc).timestamp(),
        }]
        expected_id = 'legacy-healthy'

    handle_list(menu, [])

    assert [agent.display_id for agent in menu.displayed_agents] == [expected_id]
    assert menu.load_complete is False
    assert menu.load_error is None
    assert any(str(failure) in warning for warning in menu.load_warnings)
    output = menu.console.export_text()
    assert str(failure) in output
    assert menu.displayed_agents[0].hostname in output
    handle_set(menu, ['1'])
    assert menu.selected_agent is menu.displayed_agents[0]


def test_total_inventory_failure_clears_selection_then_recovers(inventory_menu):
    menu, api = inventory_menu
    handle_list(menu, [])
    handle_set(menu, ['1'])
    assert menu.selected_agent.display_id == 'endpoint-healthy'
    menu._schedule_cache = {'ts': 1, 'items': [{'clientId': 'endpoint-healthy'}]}
    menu._remote_ls_cache[('endpoint-healthy', '/')] = (1, ['old-file'])
    menu.console.export_text()

    api.legacy_error = RuntimeError('[red]legacy unavailable[/red]')
    api.endpoint_error = RuntimeError('[blue]v2 unavailable[/blue]')
    handle_list(menu, [])

    assert menu.load_complete is False
    assert menu.load_error is not None
    assert menu.agents == []
    assert menu.displayed_agents == []
    assert menu.selected_agent is None
    assert menu.agent_lookup == {}
    assert menu.agent_os_lookup == {}
    assert menu.agent_account_map == {}
    assert menu.agent_computed_data == {}
    assert menu._schedule_cache['items'] == []
    assert menu._remote_ls_cache == {}
    output = menu.console.export_text()
    assert str(api.legacy_error) in output
    assert str(api.endpoint_error) in output

    api.legacy_error = None
    api.endpoint_error = None
    handle_list(menu, [])

    assert menu.load_complete is True
    assert menu.load_error is None
    assert menu.load_warnings == []
    assert [agent.display_id for agent in menu.displayed_agents] == ['endpoint-healthy']
    handle_set(menu, ['endpoint-healthy'])
    assert menu.selected_agent is menu.displayed_agents[0]
    output = menu.console.export_text()
    assert 'legacy unavailable' not in output
    assert 'v2 unavailable' not in output


def test_partial_empty_inventory_is_not_confirmed_empty_and_refresh_clears_warning(inventory_menu):
    menu, api = inventory_menu
    api.endpoints = []
    api.legacy_error = RuntimeError('legacy request failed')

    handle_list(menu, [])

    assert menu.agents == []
    assert menu.displayed_agents == []
    assert menu.load_complete is False
    assert menu.load_error is None
    assert any(str(api.legacy_error) in warning for warning in menu.load_warnings)
    incomplete_output = menu.console.export_text()
    assert 'incomplete' in incomplete_output.lower()

    api.legacy_error = None
    handle_list(menu, [])

    assert menu.agents == []
    assert menu.displayed_agents == []
    assert menu.load_complete is True
    assert menu.load_warnings == []
    assert menu.load_error is None
    healthy_output = menu.console.export_text()
    assert 'incomplete' not in healthy_output.lower()
    assert 'legacy request failed' not in healthy_output


@pytest.mark.parametrize('failed_source', ['legacy', 'account'])
def test_multi_account_inventory_keeps_healthy_rows_and_reports_partial_load(
    inventory_menu, monkeypatch, failed_source,
):
    menu, api = inventory_menu
    menu.multi_account_mode = True
    menu.selected_accounts = [
        {'account_email': 'healthy@example.com', 'display_name': 'Healthy'},
        {'account_email': 'other@example.com', 'display_name': 'Other'},
    ]
    assumed_accounts = []
    menu.sdk.accounts = SimpleNamespace(assume_role=assumed_accounts.append)
    menu.sdk.keychain = SimpleNamespace(
        base_url=lambda: 'https://inventory.example.com',
        headers=lambda: {},
    )
    failing = True

    def get(url, headers, params=None, timeout=None):
        other_account = headers['account'] == 'other@example.com'
        failed_account = other_account if failed_source == 'account' else not other_account
        if failing and failed_account:
            if failed_source == 'account' or url.endswith('/agent/enhanced'):
                raise RuntimeError('[red]account request failed[/red]')
        if url.endswith('/endpoint/list'):
            rows = [] if other_account else api.endpoints
            return SimpleNamespace(status_code=200, json=lambda: {'endpoints': rows})
        if url.endswith(('/agent/enhanced', '/my', '/endpoint')):
            return SimpleNamespace(status_code=200, json=lambda: [])
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests.get', get)
    handle_list(menu, [])

    assert menu.load_complete is False
    assert menu.load_error is None
    warning_account = 'other@example.com' if failed_source == 'account' else 'healthy@example.com'
    assert any(warning_account in warning for warning in menu.load_warnings)
    assert [agent.display_id for agent in menu.displayed_agents] == ['endpoint-healthy']
    output = menu.console.export_text()
    assert '[red]account request failed[/red]' in output
    handle_set(menu, ['1'])
    assert menu.selected_agent is menu.displayed_agents[0]
    assert assumed_accounts == ['healthy@example.com']
    menu.console.export_text()

    failing = False
    handle_list(menu, [])

    assert menu.load_complete is True
    assert menu.load_warnings == []
    assert menu.selected_agent is menu.displayed_agents[0]
    assert 'account request failed' not in menu.console.export_text()
