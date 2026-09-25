from copy import deepcopy

from praetorian_cli.ui.conversation.endpoint_status import (
    endpoint_status_fingerprint,
    format_endpoint_execution_status,
    format_endpoint_operation_status,
)


def test_status_formatter_distinguishes_offline_task_and_reconnecting_session():
    snapshot = {
        'sessions': [{
            'sessionId': 'session-1',
            'endpointId': 'endpoint-1',
            'taskId': 'bootstrap-1',
            'state': 'Reconnecting',
            'phase': 'reconnecting',
            'connection': {'state': 'not_connected'},
            'sandbox': {'health': 'unknown'},
            'operationCount': 1,
            'activeOperationCount': 1,
            'activeOperations': [{
                'operationId': 'operation-1',
                'tool': 'command',
                'state': 'Running',
                'stdout': 'SECRET_OUTPUT',
                'stderr': 'SECRET_ERROR',
            }],
        }],
        'tasks': [{
            'endpointId': 'endpoint-1',
            'taskId': 'task-1',
            'jobKey': '#job#1',
            'capability': 'portscan',
            'target': '#asset#internal#10.0.0.5',
            'state': 'Ready',
            'phase': 'waiting_for_endpoint',
            'endpointConnectionState': 'not_connected',
        }],
    }

    rendered = format_endpoint_execution_status(snapshot)

    assert 'Endpoint session reconnecting' in rendered
    assert 'Waiting for assigned endpoint (no compute fallback)' in rendered
    assert 'operation-1' in rendered
    assert 'SECRET_OUTPUT' not in rendered
    assert 'SECRET_ERROR' not in rendered


def test_operation_formatter_shows_artifact_metadata_but_not_output_tails():
    operation = {
        'operationId': 'operation-1',
        'sequence': 2,
        'tool': 'browser',
        'state': 'Completed',
        'updatedAt': '2026-09-04T10:00:00Z',
        'exitCode': 0,
        'stdout': 'SECRET_OUTPUT',
        'stderr': 'SECRET_ERROR',
        'artifacts': [{
            'artifactId': 'artifact-1',
            'name': 'proof.png',
            'sizeBytes': 123,
            'sha256': 'a' * 64,
        }],
    }

    rendered = format_endpoint_operation_status(operation)

    assert 'proof.png' in rendered
    assert '123 bytes' in rendered
    assert 'artifact-1' in rendered
    assert 'SECRET_OUTPUT' not in rendered
    assert 'SECRET_ERROR' not in rendered


def test_status_fingerprint_changes_with_active_operation_state():
    snapshot = {
        'sessions': [{
            'sessionId': 'session-1',
            'state': 'Ready',
            'phase': 'executing_tool',
            'updatedAt': '2026-09-04T10:00:00Z',
            'activeOperations': [{
                'operationId': 'operation-1',
                'state': 'Running',
            }],
        }],
        'tasks': [],
    }

    first = endpoint_status_fingerprint(snapshot)
    snapshot['sessions'][0]['activeOperations'][0]['state'] = 'Completed'

    assert endpoint_status_fingerprint(snapshot) != first


def test_status_fingerprint_covers_every_rendered_dynamic_field():
    snapshot = {
        'sessions': [{
            'sessionId': 'session-1',
            'connection': {'state': 'not_connected'},
            'sandbox': {'health': 'starting'},
            'activeOperationCount': 0,
            'operationCount': 0,
        }],
        'tasks': [{
            'endpointId': 'endpoint-1',
            'taskId': 'task-1',
            'endpointConnectionState': 'not_connected',
            'artifact': {'versionId': 'v1', 'sha256': 'a' * 64},
        }],
    }
    original = endpoint_status_fingerprint(snapshot)
    changes = (
        lambda value: value['sessions'][0]['connection'].__setitem__(
            'state', 'online'
        ),
        lambda value: value['sessions'][0]['sandbox'].__setitem__(
            'health', 'healthy'
        ),
        lambda value: value['sessions'][0].__setitem__(
            'activeOperationCount', 1
        ),
        lambda value: value['sessions'][0].__setitem__(
            'operationCount', 1
        ),
        lambda value: value['tasks'][0].__setitem__(
            'endpointConnectionState', 'online'
        ),
        lambda value: value['tasks'][0]['artifact'].__setitem__(
            'versionId', 'v2'
        ),
    )

    for change in changes:
        modified = deepcopy(snapshot)
        change(modified)
        assert endpoint_status_fingerprint(modified) != original


def test_status_fingerprint_ignores_output_tails_and_response_order():
    first = {
        'sessions': [{
            'sessionId': 'session-1',
            'activeOperations': [
                {'operationId': 'operation-2', 'state': 'Running'},
                {'operationId': 'operation-1', 'state': 'Running'},
            ],
        }],
        'tasks': [
            {'endpointId': 'endpoint-1', 'taskId': 'task-2'},
            {'endpointId': 'endpoint-1', 'taskId': 'task-1'},
        ],
    }
    second = deepcopy(first)
    second['sessions'][0]['activeOperations'].reverse()
    second['sessions'][0]['activeOperations'][0]['stdout'] = 'new output'
    second['tasks'].reverse()

    assert endpoint_status_fingerprint(second) == endpoint_status_fingerprint(
        first
    )
