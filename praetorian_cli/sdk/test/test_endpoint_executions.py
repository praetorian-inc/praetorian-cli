import hashlib
from pathlib import Path

import pytest

from praetorian_cli.sdk.entities.endpoint_executions import (
    EndpointExecutions,
    endpoint_task_references,
)
from praetorian_cli.sdk.entities.jobs import Jobs


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=''):
        self.status_code = status_code
        self.body = body or {}
        self.text = text
        self.ok = 200 <= status_code < 300

    def json(self):
        return self.body


class FakeFiles:
    def __init__(self, content=b'proof'):
        self.content = content
        self.calls = []

    def save_verified(self, remote_path, size, sha256, directory):
        self.calls.append((remote_path, size, sha256, directory))
        if len(self.content) != size or hashlib.sha256(self.content).hexdigest() != sha256:
            raise ValueError(
                'downloaded artifact failed size or SHA-256 verification'
            )
        local_path = Path(directory) / 'downloaded-proof'
        local_path.write_bytes(self.content)
        return str(local_path)


class FakeJobs:
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = []

    def list_by_conversation(self, conversation_id):
        self.calls.append(conversation_id)
        return list(self.jobs.get(conversation_id, [])), None


class FakeConversations:
    def tree_ids(self, conversation_id):
        assert conversation_id == 'root'
        return ['root', 'child']


class FakeAPI:
    def __init__(self, responses=None, jobs=None, file_content=b'proof'):
        self.responses = responses or {}
        self.calls = []
        self.conversations = FakeConversations()
        self.jobs = FakeJobs(jobs or {})
        self.files = FakeFiles(file_content)

    def url(self, path):
        return path

    def chariot_request(self, method, url):
        self.calls.append((method, url))
        return self.responses.get((method, url), FakeResponse(404))


def test_endpoint_status_and_cancellation_paths_are_exact_and_encoded():
    task = {'endpointId': 'endpoint/1', 'taskId': 'task 1'}
    api = FakeAPI({
        ('GET', '/endpoint/endpoint%2F1/tasks/task%201'): FakeResponse(body=task),
        ('DELETE', '/endpoint/endpoint%2F1/tasks/task%201'): FakeResponse(202, task),
    })
    executions = EndpointExecutions(api)

    assert executions.task_status('endpoint/1', 'task 1') == task
    assert executions.cancel_task('endpoint/1', 'task 1') == task
    assert api.calls == [
        ('GET', '/endpoint/endpoint%2F1/tasks/task%201'),
        ('DELETE', '/endpoint/endpoint%2F1/tasks/task%201'),
    ]


def test_conversation_session_optional_not_found_is_none():
    api = FakeAPI()

    status = EndpointExecutions(api).conversation_session_status(
        'conversation-1', optional=True
    )

    assert status is None
    assert api.calls == [(
        'GET',
        '/endpoint/conversations/conversation-1/session',
    )]


def test_endpoint_api_failure_uses_existing_sdk_error_path():
    api = FakeAPI({
        ('GET', '/endpoint/sessions/session-1'): FakeResponse(
            503, text='temporarily unavailable'
        ),
    })

    with pytest.raises(Exception, match=r'\[503\] Request failed'):
        EndpointExecutions(api).session_status('session-1')


def test_conversation_status_collects_sessions_and_unique_task_handles():
    session = {
        'sessionId': 'session-1',
        'conversationId': 'child',
        'state': 'Ready',
    }
    task = {
        'endpointId': 'endpoint-1',
        'taskId': 'task-1',
        'phase': 'running',
    }
    api = FakeAPI(
        {
            ('GET', '/endpoint/conversations/child/session'): FakeResponse(body=session),
            ('GET', '/endpoint/endpoint-1/tasks/task-1'): FakeResponse(body=task),
        },
        jobs={
            'root': [{
                'endpoint_id': 'endpoint-1',
                'endpoint_task_id': 'task-1',
            }],
            'child': [{
                'endpoint_id': 'endpoint-1',
                'endpoint_task_id': 'task-1',
            }],
        },
    )

    status = EndpointExecutions(api).conversation_status('root')

    assert status == {'sessions': [session], 'tasks': [task]}
    assert api.jobs.calls == ['root', 'child']
    assert api.calls.count(('GET', '/endpoint/endpoint-1/tasks/task-1')) == 1


def test_endpoint_task_references_ignore_incomplete_and_duplicate_handles():
    assert endpoint_task_references([
        {'endpoint_id': ' endpoint-1 ', 'endpoint_task_id': ' task-1 '},
        {'endpoint_id': 'endpoint-1', 'endpoint_task_id': 'task-1'},
        {'endpoint_id': 'endpoint-2'},
        None,
    ]) == [('endpoint-1', 'task-1')]


def test_job_list_by_conversation_uses_tenant_partition_and_pages():
    class JobAPI:
        def __init__(self):
            self.calls = []

        def get(self, path, params):
            self.calls.append((path, dict(params)))
            if len(self.calls) == 1:
                return {'jobs': [{'key': 'job-1'}], 'offset': {'key': 'next'}}
            return {'jobs': [{'key': 'job-2'}]}

    api = JobAPI()

    jobs, offset = Jobs(api).list_by_conversation(' conversation-1 ')

    assert jobs == [{'key': 'job-1'}, {'key': 'job-2'}]
    assert offset is None
    assert api.calls == [
        ('my', {'label': 'job', 'key': 'conversation:conversation-1'}),
        ('my', {
            'label': 'job',
            'key': 'conversation:conversation-1',
            'offset': '{"key": "next"}',
        }),
    ]


def test_download_operation_artifacts_verifies_server_path_size_and_sha(tmp_path):
    content = b'proof'
    digest = hashlib.sha256(content).hexdigest()
    operation = {
        'operationId': 'operation-1',
        'artifacts': [{
            'artifactId': 'artifact-1',
            'name': 'screenshots/proof.png',
            'sizeBytes': len(content),
            'sha256': digest,
        }],
    }
    api = FakeAPI({
        ('GET', '/endpoint/sessions/session-1/operations/operation-1'):
            FakeResponse(body=operation),
    }, file_content=content)

    paths = EndpointExecutions(api).download_operation_artifacts(
        'session-1', 'operation-1', str(tmp_path)
    )

    assert paths == [str(tmp_path / 'downloaded-proof')]
    assert api.files.calls == [(
        'proofs/endpoint-sessions/session-1/operation-1/'
        'artifact-1/screenshots/proof.png',
        len(content),
        digest,
        str(tmp_path),
    )]


def test_download_operation_artifacts_resolves_default_directory_at_call_time(
    monkeypatch,
    tmp_path,
):
    content = b'proof'
    operation = {
        'artifacts': [{
            'artifactId': 'artifact-1',
            'name': 'proof.txt',
            'sizeBytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(),
        }],
    }
    api = FakeAPI({
        ('GET', '/endpoint/sessions/session-1/operations/operation-1'):
            FakeResponse(body=operation),
    }, file_content=content)
    monkeypatch.chdir(tmp_path)

    paths = EndpointExecutions(api).download_operation_artifacts(
        'session-1', 'operation-1'
    )

    assert paths == [str(tmp_path / 'downloaded-proof')]


def test_failed_artifact_verification_removes_download(tmp_path):
    operation = {
        'artifacts': [{
            'artifactId': 'artifact-1',
            'name': 'proof.txt',
            'sizeBytes': 5,
            'sha256': '0' * 64,
        }],
    }
    api = FakeAPI({
        ('GET', '/endpoint/sessions/session-1/operations/operation-1'):
            FakeResponse(body=operation),
    })

    with pytest.raises(ValueError, match='failed size or SHA-256'):
        EndpointExecutions(api).download_operation_artifacts(
            'session-1', 'operation-1', str(tmp_path)
        )

    assert not (tmp_path / 'downloaded-proof').exists()
