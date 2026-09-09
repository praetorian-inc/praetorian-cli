from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from rich.console import Console

from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase
from praetorian_cli.ui.aegis.commands.list import handle_list
from praetorian_cli.ui.aegis.menu import AegisMenu

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, agents=None):
        super().__init__()
        self.agents = agents or []
        self.loaded = False
        self.show_args = []

    def load_agents(self):
        self.loaded = True
        self.agents = [object()]

    def show_agents_list(self, show_offline=False):
        self.show_args.append(show_offline)


def test_list_loads_when_empty():
    menu = Menu(agents=[])
    handle_list(menu, [])
    assert menu.loaded is True
    assert menu.show_args == [False]
    assert menu.paused is True


def test_list_with_all_flag():
    menu = Menu(agents=[object()])
    handle_list(menu, ['--all'])
    assert menu.loaded is True  # always reloads for fresh last_seen_at
    assert menu.show_args == [True]
    assert menu.paused is True


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
                return [{
                    'endpointId': 'endpoint-1',
                    'cloudflared': {'state': 'running'},
                }], None
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
            if key in (
                '#endpoint#',
                '#endpointaegistunnelstate#',
                '#endpointaegisstatus#',
            ):
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
