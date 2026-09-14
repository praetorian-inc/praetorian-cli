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


def test_hunt_cost_uses_guard_cost_contract_and_strips_key_prefix():
    class CostAPI:
        def __init__(self):
            self.paths = []

        def get(self, path):
            self.paths.append(path)
            return {
                'total': {
                    'model': '',
                    'cost': 1.25,
                    'call_count': 2,
                    'input_tokens': 100,
                    'output_tokens': 50,
                    'total_tokens': 150,
                },
                'by_model': [],
                'currency': 'USD',
            }

    api = CostAPI()

    hunt_id = '550e8400-e29b-41d4-a716-446655440000'
    result = Hunts(api).get_cost(f'#hunt#{hunt_id}')
    Hunts(api).get_cost('hunt/../../other')

    assert api.paths == [
        f'hunt/{hunt_id}/cost',
        'hunt/hunt%2F..%2F..%2Fother/cost',
    ]
    assert result['total']['cost'] == 1.25
    assert result['currency'] == 'USD'


def test_hunt_cost_requires_an_id_before_request():
    with pytest.raises(ValueError, match='hunt ID is required'):
        Hunts(SimpleNamespace()).get_cost('  ')


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


def test_hunt_request_includes_ui_launch_configuration():
    api = FakeAPI()

    Hunts(api).create(
        'Find risks',
        finish_criteria='Stop after one critical finding',
        user_guardrails='Do not authenticate',
        custom_tag='Q4-Hunt',
        model_tier_override='experimental',
        credential_ids=[
            '#credential#integration#active-directory#ad-1',
            'web-1',
        ],
    )

    body = api.calls[0]['body']
    assert body['finishCriteria'] == 'Stop after one critical finding'
    assert body['userGuardrails'] == 'Do not authenticate'
    assert body['customTag'] == 'Q4-Hunt'
    assert body['modelTierOverride'] == 'experimental'
    assert body['credentialIds'] == ['ad-1', 'web-1']


def test_hunt_request_normalizes_run_scoped_credential_references():
    api = FakeAPI()

    Hunts(api).create(
        'Assess internal services',
        scope=['#asset#internal.example#10.0.0.5'],
        endpoint_required=True,
        endpoint_id='11111111-1111-4111-8111-111111111111',
        endpoint_confirmed=True,
        credential_ids=[
            '#credential#integration#active-directory#ad-1',
            'web-1',
        ],
    )

    assert api.calls[0]['body']['credentialIds'] == ['ad-1', 'web-1']


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


def test_list_hunt_findings_uses_reported_by_relationship():
    class Search:
        def __init__(self):
            self.query = None

        def by_query(self, query, pages):
            self.query = query.to_dict()
            assert pages == 2
            return [{'key': '#risk#target#finding'}], None

    search = Search()
    findings, offset = Hunts(SimpleNamespace(search=search)).list_findings(
        'hunt-1',
        pages=2,
    )

    assert findings == [{'key': '#risk#target#finding'}]
    assert offset is None
    assert search.query['node']['labels'] == ['Risk']
    relationship = search.query['node']['relationships'][0]
    assert relationship['label'] == 'REPORTED_BY'
    assert relationship['target']['labels'] == ['Hunt']
    assert relationship['target']['filters'][0]['value'] == '#hunt#hunt-1'


def test_hunt_memory_round_trips_through_hunt_owned_routes():
    class Files:
        def __init__(self):
            self.paths = []

        def get_utf8(self, path):
            self.paths.append(path)
            return 'remembered context'

    class MemoryAPI:
        def __init__(self):
            self.files = Files()
            self.calls = []

        def put(self, path, body):
            self.calls.append(('PUT', path, body))
            return {'title': 'target notes.md'}

        def delete(self, path, body, params):
            self.calls.append(('DELETE', path, body, params))
            return {'title': 'target notes.md'}

    api = MemoryAPI()
    hunts = Hunts(api)

    assert hunts.get_memory('hunt-1', 'target notes.md') == 'remembered context'
    hunts.save_memory('hunt-1', 'target notes.md', 'new context')
    hunts.delete_memory('hunt-1', 'target notes.md')

    assert api.files.paths == ['memory/hunt/hunt-1/target notes.md']
    assert api.calls == [
        (
            'PUT',
            'hunt/hunt-1/memory/target%20notes.md',
            {'content': 'new context'},
        ),
        (
            'DELETE',
            'hunt/hunt-1/memory/target%20notes.md',
            {},
            {},
        ),
    ]


def test_list_hunt_memory_excludes_summary_log():
    class MemoryListAPI:
        def get(self, path, params):
            assert path == 'my'
            assert params == {
                'label': 'file',
                'key': '#file#memory/hunt/hunt-1/',
            }
            return {'files': [
                {'name': 'memory/hunt/hunt-1/summary.log'},
                {'name': 'memory/hunt/hunt-1/zeta.md'},
                {'name': 'memory/hunt/hunt-1/alpha.md'},
            ]}

    items, offset = Hunts(MemoryListAPI()).list_memory('hunt-1')

    assert [item['title'] for item in items] == ['alpha.md', 'zeta.md']
    assert offset is None


def test_hunt_memory_rejects_invalid_and_system_owned_titles():
    hunts = Hunts(SimpleNamespace())

    with pytest.raises(ValueError, match='memory title'):
        hunts.get_memory('hunt-1', '../secret')
    with pytest.raises(ValueError, match='system-owned'):
        hunts.save_memory('hunt-1', 'summary.log', 'overwrite')


def test_list_workflow_runs_uses_hunt_index_and_preserves_pagination():
    class WorkflowAPI:
        def __init__(self):
            self.calls = []

        def get(self, path, params):
            self.calls.append((path, dict(params)))
            if len(self.calls) == 1:
                return {
                    'workflowruns': [{'run_id': 'run-1'}],
                    'count': 2,
                    'offset': {'key': 'next'},
                }
            return {
                'workflowruns': [{'run_id': 'run-2'}],
                'count': 2,
            }

    api = WorkflowAPI()

    runs, offset = Hunts(api).list_workflow_runs('#hunt#hunt-1', pages=2)

    assert [run['run_id'] for run in runs] == ['run-1', 'run-2']
    assert offset is None
    assert api.calls == [
        ('my', {'label': 'workflow_run', 'key': 'hunt:hunt-1'}),
        ('my', {
            'label': 'workflow_run',
            'key': 'hunt:hunt-1',
            'offset': '{"key": "next"}',
        }),
    ]


def test_list_root_conversations_only_reads_hunt_iteration_index():
    class ConversationAPI:
        def __init__(self):
            self.calls = []

        def get(self, path, params):
            self.calls.append((path, dict(params)))
            return {
                'conversations': [{
                    'uuid': 'conversation-1',
                    'status': 'active',
                }],
            }

    api = ConversationAPI()

    conversations, offset = Hunts(api).list_root_conversations('hunt-1')

    assert [item['uuid'] for item in conversations] == ['conversation-1']
    assert offset is None
    assert api.calls == [(
        'my',
        {'label': 'conversation', 'key': 'hunt:hunt-1'},
    )]


def test_list_hunt_conversations_uses_tenant_hunt_index():
    class ConversationAPI:
        def __init__(self):
            self.calls = []

        def get(self, path, params):
            self.calls.append((path, dict(params)))
            if params['key'] == 'hunt:hunt-1':
                return {
                    'conversations': [{
                        'uuid': 'conversation-1',
                        'status': 'active',
                    }],
                    'count': 1,
                }
            if params['key'] == 'parent_id:conversation-1':
                return {
                    'conversations': [{
                        'uuid': 'subagent-1',
                        'parent_id': 'conversation-1',
                    }],
                }
            return {'conversations': []}

    api = ConversationAPI()

    conversations, offset = Hunts(api).list_conversations('hunt-1')

    assert [item['uuid'] for item in conversations] == [
        'conversation-1',
        'subagent-1',
    ]
    assert offset is None
    assert api.calls == [
        (
            'my',
            {'label': 'conversation', 'key': 'hunt:hunt-1'},
        ),
        (
            'my',
            {
                'label': 'conversation',
                'key': 'parent_id:conversation-1',
                'user': False,
            },
        ),
        (
            'my',
            {
                'label': 'conversation',
                'key': 'parent_id:subagent-1',
                'user': False,
            },
        ),
    ]


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
