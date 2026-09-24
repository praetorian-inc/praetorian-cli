import pytest

from praetorian_cli.sdk.entities.aegis import Aegis


POLICY = {
    'endpointId': 'endpoint/one',
    'revision': 3,
    'disabledDefaultRuleIds': ['deny-loopback'],
    'customDenyRules': [{'destination': '10.0.0.0/24', 'tcpPorts': [22, 443]}],
}


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get(self, path):
        self.calls.append(('GET', path))
        return POLICY

    def put(self, path, body):
        self.calls.append(('PUT', path, body))
        return {**POLICY, **body, 'revision': 4}


def test_get_endpoint_network_policy_uses_encoded_endpoint_id():
    api = FakeAPI()

    result = Aegis(api).get_endpoint_network_policy(' endpoint/one ')

    assert result == POLICY
    assert api.calls == [('GET', 'endpoint/endpoint%2Fone/network-policy')]


def test_update_endpoint_network_policy_sends_revision_and_complete_policy():
    api = FakeAPI()
    disabled = ['deny-loopback']
    rules = [{'destination': '10.0.0.0/24', 'tcpPorts': [443, 22]}]

    Aegis(api).update_endpoint_network_policy(
        'endpoint-1',
        3,
        disabled,
        rules,
    )

    assert api.calls == [('PUT', 'endpoint/endpoint-1/network-policy', {
        'expectedRevision': 3,
        'disabledDefaultRuleIds': ['deny-loopback'],
        'customDenyRules': [
            {'destination': '10.0.0.0/24', 'tcpPorts': [443, 22]},
        ],
    })]
    assert disabled == ['deny-loopback']
    assert rules == [{'destination': '10.0.0.0/24', 'tcpPorts': [443, 22]}]


@pytest.mark.parametrize('method', [
    'get_endpoint_network_policy',
    'update_endpoint_network_policy',
])
def test_endpoint_network_policy_methods_require_endpoint_id(method):
    aegis = Aegis(FakeAPI())
    arguments = () if method == 'get_endpoint_network_policy' else (0, [], [])

    with pytest.raises(ValueError, match='endpoint ID is required'):
        getattr(aegis, method)('  ', *arguments)


@pytest.mark.parametrize('revision', [-1, True, '1'])
def test_update_endpoint_network_policy_requires_valid_revision(revision):
    with pytest.raises(ValueError, match='non-negative integer'):
        Aegis(FakeAPI()).update_endpoint_network_policy(
            'endpoint-1',
            revision,
            [],
            [],
        )
