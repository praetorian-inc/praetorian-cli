from types import SimpleNamespace

from click.testing import CliRunner

from praetorian_cli.handlers.hunt import hunt
from praetorian_cli.sdk.model.aegis import Agent


ENDPOINT_ID = '11111111-1111-4111-8111-111111111111'
SCOPE = '#asset#internal.example#10.0.0.5'


class FakeHunts:
    def __init__(self):
        self.create_calls = []
        self.hunt = None

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {'uuid': 'hunt-1', **kwargs}

    def get(self, _uuid):
        return self.hunt


class FakeAegis:
    def __init__(self, agents):
        self.agents = agents

    def list_hunt_endpoints(self):
        return list(self.agents)


def _endpoint(hostname='aegis-internal', endpoint_id=ENDPOINT_ID):
    return Agent.from_endpoint_dict({
        'endpointId': endpoint_id,
        'kind': 'aegis',
        'hostname': hostname,
    })


def _sdk(agents=None):
    return SimpleNamespace(
        hunts=FakeHunts(),
        aegis=FakeAegis(agents if agents is not None else [_endpoint()]),
    )


def _launch_args(*extra):
    return [
        'launch',
        '--prompt', 'Assess internal services',
        '--scope', SCOPE,
        *extra,
    ]


def test_internal_hunt_cli_sends_confirmed_endpoint_contract():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args(
            '--internal',
            '--endpoint', ENDPOINT_ID,
            '--confirm-endpoint',
        ),
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls == [{
        'prompt': 'Assess internal services',
        'expires_hours': 72,
        'agent': 'hannibal',
        'scope': [SCOPE],
        'scope_level': 'normal',
        'aggressiveness': 'balanced',
        'endpoint_required': True,
        'endpoint_id': ENDPOINT_ID,
        'endpoint_confirmed': True,
    }]


def test_internal_hunt_cli_confirmation_names_offline_no_fallback_policy():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--endpoint', 'aegis-internal'),
        obj=sdk,
        input='y\n',
    )

    assert result.exit_code == 0, result.output
    assert 'aegis-internal' in result.output
    assert ENDPOINT_ID in result.output
    assert 'offline' in result.output
    assert 'waits without Guard compute fallback' in result.output
    assert sdk.hunts.create_calls[0]['endpoint_confirmed'] is True


def test_internal_hunt_cli_can_select_an_authorized_v2_endpoint():
    second_id = '22222222-2222-4222-8222-222222222222'
    sdk = _sdk([_endpoint('first'), _endpoint('second', second_id)])

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal'),
        obj=sdk,
        input='2\ny\n',
    )

    assert result.exit_code == 0, result.output
    assert 'Authorized Aegis v2 endpoints' in result.output
    assert sdk.hunts.create_calls[0]['endpoint_id'] == second_id


def test_internal_hunt_endpoint_id_takes_priority_over_matching_hostname():
    second_id = '22222222-2222-4222-8222-222222222222'
    sdk = _sdk([
        _endpoint(second_id, ENDPOINT_ID),
        _endpoint('second', second_id),
    ])

    result = CliRunner().invoke(
        hunt,
        _launch_args(
            '--internal',
            '--endpoint', second_id,
            '--confirm-endpoint',
        ),
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls[0]['endpoint_id'] == second_id


def test_internal_hunt_cli_rejects_endpoint_options_without_internal_mode():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args('--endpoint', ENDPOINT_ID),
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'require --internal' in result.output
    assert sdk.hunts.create_calls == []


def test_internal_hunt_cli_requires_hannibal_and_scope():
    sdk = _sdk()

    wrong_agent = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--agent', 'hannibal-webapp'),
        obj=sdk,
    )
    no_scope = CliRunner().invoke(
        hunt,
        ['launch', '--prompt', 'test', '--internal'],
        obj=sdk,
    )

    assert wrong_agent.exit_code != 0
    assert 'requires the hannibal infrastructure agent' in wrong_agent.output
    assert no_scope.exit_code != 0
    assert 'requires at least one --scope' in no_scope.output
    assert sdk.hunts.create_calls == []


def test_internal_hunt_cli_rejects_legacy_aegis_agent():
    sdk = _sdk([Agent(client_id='C.legacy', hostname='legacy')])

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--endpoint', 'C.legacy'),
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'No authorized Aegis v2 endpoints' in result.output
    assert sdk.hunts.create_calls == []


def test_hunt_status_includes_internal_execution_placement():
    sdk = _sdk()
    sdk.hunts.hunt = {
        'uuid': 'hunt-1',
        'status': 'active',
        'agent': 'hannibal',
        'endpointRequired': True,
        'endpointId': ENDPOINT_ID,
        'currentWorkflowRunId': 'workflow-1',
    }

    result = CliRunner().invoke(hunt, ['status', 'hunt-1'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert '"endpointRequired": true' in result.output
    assert f'"endpointId": "{ENDPOINT_ID}"' in result.output
    assert '"currentWorkflowRunId": "workflow-1"' in result.output
