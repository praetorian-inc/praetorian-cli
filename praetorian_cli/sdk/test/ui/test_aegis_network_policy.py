from copy import deepcopy

import pytest
from rich.console import Console

from praetorian_cli.sdk.test.test_aegis_network_policy import POLICY
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK
from praetorian_cli.ui.aegis import menu as menu_module
from praetorian_cli.ui.aegis.menu import AegisMenu
from praetorian_cli.ui.aegis.commands.network_policy import (
    complete,
    handle_network_policy,
)


pytestmark = pytest.mark.tui


class V2Endpoint:
    hostname = 'sensor'
    endpoint_id = 'endpoint-1'
    version = 'v2'
    network_policy_supported = True

    @property
    def client_id(self):
        raise AssertionError('v2 policy commands must not inspect legacy client_id')


class V1Agent:
    hostname = 'legacy'
    client_id = 'C.1'
    endpoint_id = None
    version = 'v1'


class Menu(MockMenuBase):
    def __init__(self, selected_agent=None, policy=None):
        super().__init__()
        self.sdk = MockSDK({'network_policy': deepcopy(policy or POLICY)})
        self.selected_agent = selected_agent


def test_policy_without_arguments_shows_all_policy_sections():
    menu = Menu(V2Endpoint())
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_network_policy(menu, [])

    output = menu.console.export_text()
    assert 'Endpoint Network Policy' in output
    assert 'Protected connectivity:' in output
    assert 'Default deny rules:' in output
    assert 'Custom deny rules:' in output
    assert 'deny-control-plane' in output
    assert '10.20.30.0/24 · TCP 22, 443' in output
    assert menu.sdk.aegis.calls == [{
        'method': 'get_endpoint_network_policy',
        'endpoint_id': 'endpoint-1',
    }]


def test_policy_removes_default_rule_from_selected_endpoint():
    menu = Menu(V2Endpoint())

    handle_network_policy(menu, [
        'default', 'remove', 'deny-control-plane', '--yes',
    ])

    assert menu.sdk.aegis.calls[1] == {
        'method': 'update_endpoint_network_policy',
        'endpoint_id': 'endpoint-1',
        'expected_revision': 3,
        'disabled_default_rule_ids': [
            'deny-control-plane',
            'deny-loopback',
        ],
        'custom_deny_rules': POLICY['customDenyRules'],
    }


def test_policy_adds_port_scoped_custom_rule():
    menu = Menu(V2Endpoint())

    handle_network_policy(menu, [
        'deny', 'add', '198.51.100.7', '--tcp-ports', '443,22', '--yes',
    ])

    assert menu.sdk.aegis.calls[1]['custom_deny_rules'] == [
        {'destination': '10.20.30.0/24', 'tcpPorts': [22, 443]},
        {'destination': '198.51.100.7', 'tcpPorts': [22, 443]},
        {'destination': '2001:db8::7'},
    ]


def test_policy_removes_custom_rule_by_number():
    menu = Menu(V2Endpoint())

    handle_network_policy(menu, ['deny', 'remove', '2', '--yes'])

    assert menu.sdk.aegis.calls[1]['custom_deny_rules'] == [
        {'destination': '10.20.30.0/24', 'tcpPorts': [22, 443]},
    ]


@pytest.mark.parametrize(
    ('supported', 'expected'),
    [
        (False, 'agent upgrade required'),
        (None, 'capability is unknown'),
    ],
)
def test_policy_is_read_only_when_agent_support_is_unavailable(supported, expected):
    endpoint = V2Endpoint()
    endpoint.network_policy_supported = supported
    menu = Menu(endpoint)

    handle_network_policy(menu, [
        'deny', 'add', '198.51.100.7', '--yes',
    ])

    assert len(menu.sdk.aegis.calls) == 1
    assert expected in '\n'.join(menu.console.lines)


def test_policy_rejects_legacy_agent_before_request():
    menu = Menu(V1Agent())

    handle_network_policy(menu, [])

    assert menu.sdk.aegis.calls == []
    assert 'only for Aegis v2 endpoints' in '\n'.join(menu.console.lines)


def test_aegis_menu_registers_and_dispatches_policy(monkeypatch):
    sdk = type('SDK', (), {
        'get_current_user': lambda _self: ('user@example.com', 'user'),
    })()
    menu = AegisMenu(sdk)
    calls = []
    monkeypatch.setattr(
        menu_module,
        'cmd_handle_network_policy',
        lambda received_menu, args: calls.append((received_menu, args)),
    )

    result = menu.handle_choice('policy deny add 10.0.0.7 --yes')

    assert 'policy' in menu.commands
    assert result is True
    assert calls == [(menu, ['deny', 'add', '10.0.0.7', '--yes'])]


def test_policy_completion_exposes_all_editor_actions():
    menu = Menu(V2Endpoint())

    assert complete(menu, 'd', ['policy']) == ['default', 'deny']
    assert complete(menu, 'r', ['policy', 'default']) == ['remove', 'restore']
    assert complete(menu, 'deny-', ['policy', 'default', 'remove']) == [
        'deny-unspecified',
        'deny-loopback',
        'deny-docker-api',
        'deny-control-plane',
    ]
    assert complete(menu, '--t', ['policy', 'deny', 'add', '10.0.0.7']) == [
        '--tcp-ports',
    ]
