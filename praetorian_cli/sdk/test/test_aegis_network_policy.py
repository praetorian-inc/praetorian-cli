from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.aegis  # noqa: F401 - registers aegis commands on chariot
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.ui.aegis.commands.network_policy import (
    canonical_destination,
    parse_tcp_ports,
)


POLICY = {
    'endpointId': 'endpoint-1',
    'schemaVersion': 1,
    'catalogVersion': 1,
    'revision': 3,
    'disabledDefaultRuleIds': ['deny-loopback'],
    'customDenyRules': [
        {'destination': '10.20.30.0/24', 'tcpPorts': [22, 443]},
        {'destination': '2001:db8::7'},
    ],
    'defaultRules': [
        {
            'id': 'deny-unspecified',
            'label': 'Unspecified address space',
            'description': 'Blocks the unspecified IPv4 address.',
            'enabled': True,
            'rules': [{'destination': '0.0.0.0/32'}],
        },
        {
            'id': 'deny-loopback',
            'label': 'Host loopback',
            'description': 'Blocks host loopback destinations.',
            'enabled': False,
            'rules': [
                {'destination': '127.0.0.0/8'},
                {'destination': '::1/128'},
            ],
        },
        {
            'id': 'deny-docker-api',
            'label': 'Docker API',
            'description': 'Blocks local Docker API ports.',
            'enabled': True,
        },
        {
            'id': 'deny-control-plane',
            'label': 'Guard control plane',
            'description': 'Blocks resolved Guard control addresses.',
            'enabled': True,
        },
    ],
    'protectedConnectivity': {
        'schemaVersion': 1,
        'addresses': [
            {'category': 'gateway', 'address': '10.0.0.1'},
            {'category': 'dns', 'address': '10.0.0.53'},
        ],
        'observedAt': '2026-09-15T12:00:00Z',
        'complete': True,
    },
    'validationStatus': 'validated',
    'appliedRevision': 2,
    'applicationStatus': 'applied',
    'updatedAt': '2026-09-15T12:01:00Z',
}


class FakeAegis:
    def __init__(self, error=None):
        self.policy = deepcopy(POLICY)
        self.error = error
        self.calls = []

    def get_endpoint_network_policy(self, endpoint_id):
        self.calls.append(('get', endpoint_id))
        if self.error:
            raise self.error
        return deepcopy(self.policy)

    def update_endpoint_network_policy(
        self,
        endpoint_id,
        expected_revision,
        disabled_default_rule_ids,
        custom_deny_rules,
    ):
        self.calls.append((
            'update',
            endpoint_id,
            expected_revision,
            deepcopy(disabled_default_rule_ids),
            deepcopy(custom_deny_rules),
        ))
        self.policy['revision'] = expected_revision + 1
        self.policy['disabledDefaultRuleIds'] = list(disabled_default_rule_ids)
        self.policy['customDenyRules'] = deepcopy(custom_deny_rules)
        return deepcopy(self.policy)


class FakeSDK:
    def __init__(self, aegis=None):
        self.aegis = aegis or FakeAegis()


def invoke(fake_sdk, argv, input_text=''):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda function: function):
        return CliRunner().invoke(
            chariot,
            argv,
            obj=obj,
            input=input_text,
            catch_exceptions=False,
        )


def test_cli_network_policy_show_includes_every_ui_section():
    result = invoke(FakeSDK(), [
        'aegis', 'network-policy', 'show', 'endpoint-1',
    ])

    assert result.exit_code == 0
    assert 'Desired revision: 3' in result.output
    assert 'Applied revision: 2' in result.output
    assert 'Application: Applying' in result.output
    assert 'Host validation: Validated' in result.output
    assert 'Gateway: 10.0.0.1' in result.output
    assert '[removed] deny-loopback: Host loopback' in result.output
    assert '1. 10.20.30.0/24 · TCP 22, 443' in result.output
    assert '2. 2001:db8::7 · all traffic' in result.output


def test_cli_network_policy_removes_sensitive_default_with_warning_and_revision():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'default', 'remove',
        'endpoint-1', 'deny-control-plane',
    ], input_text='y\n')

    assert result.exit_code == 0
    assert 'may expose host or Guard control services' in result.output
    assert aegis.calls[1][:4] == (
        'update',
        'endpoint-1',
        3,
        ['deny-control-plane', 'deny-loopback'],
    )
    assert aegis.calls[1][4] == POLICY['customDenyRules']


def test_cli_network_policy_restores_default_without_changing_custom_rules():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'default', 'restore',
        'endpoint-1', 'deny-loopback', '--yes',
    ])

    assert result.exit_code == 0
    assert aegis.calls[1] == (
        'update',
        'endpoint-1',
        3,
        [],
        POLICY['customDenyRules'],
    )


def test_cli_network_policy_adds_canonical_rule_with_sorted_ports():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'deny', 'add',
        'endpoint-1', '2001:0db8:1::/64', '--tcp-ports', '443,22', '--yes',
    ])

    assert result.exit_code == 0
    assert aegis.calls[1][4] == [
        {'destination': '10.20.30.0/24', 'tcpPorts': [22, 443]},
        {'destination': '2001:db8:1::/64', 'tcpPorts': [22, 443]},
        {'destination': '2001:db8::7'},
    ]


def test_cli_network_policy_removes_custom_rule_by_displayed_number():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'deny', 'remove',
        'endpoint-1', '1', '--yes',
    ])

    assert result.exit_code == 0
    assert aegis.calls[1][4] == [{'destination': '2001:db8::7'}]


def test_cli_network_policy_removes_exact_port_scoped_rule():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'deny', 'remove',
        'endpoint-1', '10.20.30.0/24', '--tcp-ports', '443,22', '--yes',
    ])

    assert result.exit_code == 0
    assert aegis.calls[1][4] == [{'destination': '2001:db8::7'}]


def test_cli_network_policy_cancel_does_not_update():
    aegis = FakeAegis()

    result = invoke(FakeSDK(aegis), [
        'aegis', 'network-policy', 'deny', 'add',
        'endpoint-1', '198.51.100.7',
    ], input_text='n\n')

    assert result.exit_code == 0
    assert aegis.calls == [('get', 'endpoint-1')]
    assert 'Cancelled' in result.output


@pytest.mark.parametrize('destination', [
    'example.com',
    '10.0.0.7/24',
    '0.0.0.0/0',
    '::ffff:192.0.2.1',
    'fe80::1%eth0',
])
def test_canonical_destination_rejects_values_the_ui_rejects(destination):
    with pytest.raises(ValueError, match='canonical IP address or CIDR'):
        canonical_destination(destination)


@pytest.mark.parametrize('ports', ['22,22', '0', '65536', 'ssh', '22,'])
def test_parse_tcp_ports_rejects_values_the_ui_rejects(ports):
    with pytest.raises(ValueError, match='unique numbers'):
        parse_tcp_ports(ports)


def test_cli_network_policy_maps_protected_connectivity_conflict():
    error = RuntimeError(
        '[422] Request failed\nError: '
        '{"error":"network_policy_fundamental_conflict",'
        '"rule":"10.0.0.0/24","category":"dns","address":"10.0.0.53"}'
    )

    result = invoke(FakeSDK(FakeAegis(error)), [
        'aegis', 'network-policy', 'show', 'endpoint-1',
    ])

    assert result.exit_code == 1
    assert 'protected Dns address 10.0.0.53' in result.output
    assert 'Request failed' not in result.output
