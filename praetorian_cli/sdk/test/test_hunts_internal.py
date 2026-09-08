from types import SimpleNamespace

import pytest

from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.entities.hunts import Hunts


class EndpointAPI:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        return self.response


class FakeAPI:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def post(self, path, body):
        self.calls.append({'path': path, 'body': dict(body)})
        if self.error:
            raise self.error
        return {'uuid': 'hunt-1', **body}


def test_list_hunt_endpoints_uses_active_identity_route():
    api = EndpointAPI([{
        'endpoint_id': '11111111-1111-4111-8111-111111111111',
        'hostname': 'aegis-internal',
        'last_heartbeat': '2026-09-04T10:00:00Z',
        'online': True,
    }])

    endpoints = Aegis(api).list_hunt_endpoints()

    assert api.calls == ['endpoint']
    assert len(endpoints) == 1
    assert endpoints[0].endpoint_id == '11111111-1111-4111-8111-111111111111'
    assert endpoints[0].hostname == 'aegis-internal'
    assert endpoints[0].is_v2


def test_external_hunt_request_does_not_include_endpoint_placement():
    api = FakeAPI()

    result = Hunts(api).create('Find risks', expires_hours=1)

    body = api.calls[0]['body']
    assert api.calls[0]['path'] == 'hunt'
    assert body['prompt'] == 'Find risks'
    assert body['agent'] == 'hannibal'
    assert body['scopeLevel'] == 'normal'
    assert 'endpointRequired' not in body
    assert 'endpointId' not in body
    assert 'endpointConfirmed' not in body
    assert result['uuid'] == 'hunt-1'


def test_internal_hunt_request_matches_guard_contract():
    api = FakeAPI()

    Hunts(api).create(
        'Assess internal services',
        expires_hours=8,
        scope=['#asset#internal.example#10.0.0.5'],
        endpoint_required=True,
        endpoint_id=' 11111111-1111-4111-8111-111111111111 ',
        endpoint_confirmed=True,
    )

    body = api.calls[0]['body']
    assert body['scope'] == ['#asset#internal.example#10.0.0.5']
    assert body['endpointRequired'] is True
    assert body['endpointId'] == '11111111-1111-4111-8111-111111111111'
    assert body['endpointConfirmed'] is True


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [
        ({'endpoint_id': 'endpoint-1'}, 'only valid for an Internal Hunt'),
        ({'endpoint_confirmed': True}, 'only valid for an Internal Hunt'),
        ({'endpoint_required': True, 'endpoint_confirmed': True, 'scope': ['asset']},
         'endpoint_id is required'),
        ({'endpoint_required': True, 'endpoint_id': 'endpoint-1', 'scope': ['asset']},
         'endpoint confirmation is required'),
        ({
            'endpoint_required': True,
            'endpoint_id': 'endpoint-1',
            'endpoint_confirmed': True,
            'scope': ['asset'],
            'agent': 'hannibal-webapp',
        }, 'requires the Hannibal infrastructure agent'),
        ({
            'endpoint_required': True,
            'endpoint_id': 'endpoint-1',
            'endpoint_confirmed': True,
        }, 'requires explicit internal scope'),
    ],
)
def test_invalid_endpoint_placement_fails_before_request(kwargs, message):
    api = FakeAPI()

    with pytest.raises(ValueError, match=message):
        Hunts(api).create('test', **kwargs)

    assert api.calls == []


def test_hunt_endpoint_status_uses_current_workflow_conversations():
    class Search:
        def by_exact_key(self, key):
            assert key == '#workflow_run#workflow-1'
            return {'steps': [
                {'conversation_id': 'conversation-1'},
                {'conversation_id': 'conversation-1'},
                {'conversation_id': 'conversation-2'},
            ]}

    class Executions:
        def __init__(self):
            self.calls = []

        def conversation_status(self, conversation_id, include_descendants=True):
            self.calls.append((conversation_id, include_descendants))
            return {
                'sessions': [{
                    'sessionId': f'session-{conversation_id}',
                }],
                'tasks': [{
                    'endpointId': 'endpoint-1',
                    'taskId': 'task-1',
                }],
            }

    executions = Executions()
    api = SimpleNamespace(search=Search(), endpoint_executions=executions)

    status = Hunts(api).endpoint_execution_status({
        'endpointRequired': True,
        'currentWorkflowRunId': 'workflow-1',
    })

    assert executions.calls == [
        ('conversation-1', False),
        ('conversation-2', False),
    ]
    assert len(status['sessions']) == 2
    assert status['tasks'] == [{
        'endpointId': 'endpoint-1',
        'taskId': 'task-1',
    }]


def test_internal_hunt_api_failure_is_propagated():
    api = FakeAPI(RuntimeError('[400] scope target is not internal'))

    with pytest.raises(RuntimeError, match='scope target is not internal'):
        Hunts(api).create(
            'test',
            scope=['#asset#external.example#198.51.100.1'],
            endpoint_required=True,
            endpoint_id='endpoint-1',
            endpoint_confirmed=True,
        )
