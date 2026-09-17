import os
import posixpath
from urllib.parse import quote


class EndpointExecutions:
    """Read and control Guard-owned endpoint tasks, sessions, and operations."""

    def __init__(self, api):
        self.api = api

    def task_status(self, endpoint_id, task_id):
        return self._get(self._task_path(endpoint_id, task_id))

    def cancel_task(self, endpoint_id, task_id):
        return self._delete(self._task_path(endpoint_id, task_id))

    def conversation_session_status(self, conversation_id, optional=False):
        conversation_id = _required_id(conversation_id, 'conversation ID')
        path = f'endpoint/conversations/{_encoded(conversation_id)}/session'
        return self._get(path, optional=optional)

    def cancel_conversation_session(self, conversation_id):
        conversation_id = _required_id(conversation_id, 'conversation ID')
        path = f'endpoint/conversations/{_encoded(conversation_id)}/session'
        return self._delete(path)

    def session_status(self, session_id):
        session_id = _required_id(session_id, 'session ID')
        return self._get(f'endpoint/sessions/{_encoded(session_id)}')

    def cancel_session(self, session_id):
        session_id = _required_id(session_id, 'session ID')
        return self._delete(f'endpoint/sessions/{_encoded(session_id)}')

    def operation_status(self, session_id, operation_id):
        return self._get(self._operation_path(session_id, operation_id))

    def cancel_operation(self, session_id, operation_id):
        return self._delete(self._operation_path(session_id, operation_id))

    def download_operation_artifacts(
        self,
        session_id,
        operation_id,
        download_directory=None,
    ):
        session_id = _required_id(session_id, 'session ID')
        operation_id = _required_id(operation_id, 'operation ID')
        download_directory = download_directory or os.getcwd()
        operation = self.operation_status(session_id, operation_id)
        downloaded = []
        for artifact in operation.get('artifacts', []):
            artifact_id = _required_id(
                artifact.get('artifactId'), 'artifact ID'
            )
            name = _artifact_name(artifact.get('name'))
            remote_path = posixpath.join(
                'proofs/endpoint-sessions',
                session_id,
                operation_id,
                artifact_id,
                name,
            )
            local_path = self.api.files.save_verified(
                remote_path,
                artifact.get('sizeBytes'),
                artifact.get('sha256'),
                download_directory,
            )
            downloaded.append(local_path)
        return downloaded

    def conversation_status(self, conversation_id, include_descendants=True):
        conversation_ids = (
            self.api.conversations.tree_ids(conversation_id)
            if include_descendants
            else [_required_id(conversation_id, 'conversation ID')]
        )
        sessions = []
        task_references = {}
        for current_id in conversation_ids:
            session = self.conversation_session_status(current_id, optional=True)
            if session:
                sessions.append(session)
            jobs, _ = self.api.jobs.list_by_conversation(current_id)
            for endpoint_id, task_id in endpoint_task_references(jobs):
                task_references[(endpoint_id, task_id)] = None

        tasks = []
        for endpoint_id, task_id in task_references:
            task = self._get(
                self._task_path(endpoint_id, task_id),
                optional=True,
            )
            if task:
                tasks.append(task)
        return {'sessions': sessions, 'tasks': tasks}

    def _task_path(self, endpoint_id, task_id):
        endpoint_id = _required_id(endpoint_id, 'endpoint ID')
        task_id = _required_id(task_id, 'task ID')
        return f'endpoint/{_encoded(endpoint_id)}/tasks/{_encoded(task_id)}'

    def _operation_path(self, session_id, operation_id):
        session_id = _required_id(session_id, 'session ID')
        operation_id = _required_id(operation_id, 'operation ID')
        return (
            f'endpoint/sessions/{_encoded(session_id)}/operations/'
            f'{_encoded(operation_id)}'
        )

    def _get(self, path, optional=False):
        from praetorian_cli.sdk.chariot import process_failure

        response = self.api.chariot_request('GET', self.api.url(f'/{path}'))
        if optional and response.status_code == 404:
            return None
        process_failure(response)
        return response.json()

    def _delete(self, path):
        from praetorian_cli.sdk.chariot import process_failure

        response = self.api.chariot_request('DELETE', self.api.url(f'/{path}'))
        process_failure(response)
        return response.json()


def endpoint_status_fingerprint(snapshot):
    """Fingerprint rendered status fields while ignoring output tails."""
    snapshot = snapshot or {}
    sessions = tuple(sorted(
        _session_fingerprint(row)
        for row in snapshot.get('sessions', [])
        if isinstance(row, dict)
    ))
    tasks = tuple(sorted(
        _task_fingerprint(row)
        for row in snapshot.get('tasks', [])
        if isinstance(row, dict)
    ))
    return sessions, tasks


def endpoint_task_references(jobs):
    references = []
    seen = set()
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        endpoint_id = _optional_id(job.get('endpoint_id'))
        task_id = _optional_id(job.get('endpoint_task_id'))
        reference = (endpoint_id, task_id)
        if not endpoint_id or not task_id or reference in seen:
            continue
        seen.add(reference)
        references.append(reference)
    return references


def _session_fingerprint(session):
    connection = session.get('connection') or {}
    sandbox = session.get('sandbox') or {}
    operations = tuple(sorted(
        (
            _fingerprint_value(operation.get('operationId')),
            _fingerprint_value(operation.get('tool')),
            _fingerprint_value(operation.get('state')),
            _fingerprint_value(operation.get('failureCode')),
        )
        for operation in session.get('activeOperations', [])
        if isinstance(operation, dict)
    ))
    return (
        _fingerprint_value(session.get('sessionId')),
        _fingerprint_value(session.get('endpointId')),
        _fingerprint_value(session.get('taskId')),
        _fingerprint_value(session.get('state')),
        _fingerprint_value(session.get('phase')),
        _fingerprint_value(connection.get('state')),
        _fingerprint_value(sandbox.get('health')),
        _fingerprint_value(session.get('activeOperationCount', 0)),
        _fingerprint_value(session.get('operationCount', 0)),
        _fingerprint_value(session.get('workflowRunId')),
        _fingerprint_value(session.get('failureCode')),
        operations,
    )


def _task_fingerprint(task):
    artifact = task.get('artifact') or {}
    return (
        _fingerprint_value(task.get('endpointId')),
        _fingerprint_value(task.get('taskId')),
        _fingerprint_value(task.get('jobKey')),
        _fingerprint_value(task.get('capability')),
        _fingerprint_value(task.get('target')),
        _fingerprint_value(task.get('state')),
        _fingerprint_value(task.get('phase')),
        _fingerprint_value(task.get('endpointConnectionState')),
        _fingerprint_value(task.get('failureCode')),
        _fingerprint_value(artifact.get('versionId')),
        _fingerprint_value(artifact.get('sha256')),
    )


def _fingerprint_value(value):
    return '' if value is None else str(value)


def _required_id(value, name):
    value = _optional_id(value)
    if not value:
        raise ValueError(f'{name} is required')
    return value


def _optional_id(value):
    return value.strip() if isinstance(value, str) else ''


def _artifact_name(value):
    value = value.strip() if isinstance(value, str) else ''
    clean = posixpath.normpath(value)
    if (
        not value
        or value != clean
        or posixpath.isabs(clean)
        or clean == '..'
        or clean.startswith('../')
    ):
        raise ValueError('artifact name is invalid')
    return value


def _encoded(value):
    return quote(value, safe='')
