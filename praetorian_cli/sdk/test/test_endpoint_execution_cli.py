from types import SimpleNamespace

from click.testing import CliRunner

from praetorian_cli.handlers.agent import agent


class FakeEndpointExecutions:
    def __init__(self):
        self.calls = []

    def conversation_status(self, conversation_id):
        self.calls.append(('status', conversation_id))
        return {
            'sessions': [{
                'sessionId': 'session-1',
                'endpointId': 'endpoint-1',
                'taskId': 'bootstrap-1',
                'state': 'Ready',
                'phase': 'ready',
                'connection': {'state': 'connected'},
                'sandbox': {'health': 'healthy'},
                'operationCount': 0,
                'activeOperationCount': 0,
                'activeOperations': [],
            }],
            'tasks': [],
        }

    def operation_status(self, session_id, operation_id):
        self.calls.append(('operation', session_id, operation_id))
        return {
            'operationId': operation_id,
            'sequence': 1,
            'tool': 'command',
            'state': 'Completed',
            'stdout': 'SECRET_OUTPUT',
            'artifacts': [],
        }

    def download_operation_artifacts(self, session_id, operation_id, directory):
        self.calls.append(('download', session_id, operation_id, directory))
        return [f'{directory}/proof.txt']

    def cancel_conversation_session(self, conversation_id):
        self.calls.append(('cancel-session', conversation_id))
        return self.conversation_status(conversation_id)['sessions'][0]

    def cancel_task(self, endpoint_id, task_id):
        self.calls.append(('cancel-task', endpoint_id, task_id))
        return {
            'endpointId': endpoint_id,
            'taskId': task_id,
            'jobKey': '#job#1',
            'capability': 'portscan',
            'target': '#asset#internal#10.0.0.5',
            'state': 'Claimed',
            'phase': 'cancel_requested',
            'endpointConnectionState': 'online',
        }

    def cancel_operation(self, session_id, operation_id):
        self.calls.append(('cancel-operation', session_id, operation_id))
        return self.operation_status(session_id, operation_id)


class FakeConversations:
    def __init__(self):
        self.calls = []

    def stop(self, conversation_id):
        self.calls.append(conversation_id)
        return {'status': 'stopping', 'cancelledJobs': 2}


def _sdk():
    return SimpleNamespace(
        endpoint_executions=FakeEndpointExecutions(),
        conversations=FakeConversations(),
    )


def test_endpoint_status_command_renders_conversation_execution():
    sdk = _sdk()

    result = CliRunner().invoke(
        agent, ['endpoint', 'status', 'conversation-1'], obj=sdk
    )

    assert result.exit_code == 0, result.output
    assert 'Endpoint session ready' in result.output
    assert 'session-1' in result.output
    assert sdk.endpoint_executions.calls == [('status', 'conversation-1')]


def test_endpoint_operation_command_omits_tails_and_downloads_verified_artifacts(tmp_path):
    sdk = _sdk()

    result = CliRunner().invoke(
        agent,
        [
            'endpoint', 'operation', 'session-1', 'operation-1',
            '--download', str(tmp_path),
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'Endpoint operation operation-1' in result.output
    assert 'SECRET_OUTPUT' not in result.output
    assert f'Downloaded and verified: {tmp_path}/proof.txt' in result.output


def test_endpoint_cancel_commands_require_confirmation():
    sdk = _sdk()

    denied = CliRunner().invoke(
        agent,
        ['endpoint', 'cancel-task', 'endpoint-1', 'task-1'],
        obj=sdk,
        input='n\n',
    )

    assert denied.exit_code != 0
    assert sdk.endpoint_executions.calls == []


def test_stop_conversation_uses_guard_cancellation_bridge():
    sdk = _sdk()

    result = CliRunner().invoke(
        agent,
        ['endpoint', 'stop-conversation', 'conversation-1', '--yes'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.conversations.calls == ['conversation-1']
    assert '"status": "stopping"' in result.output
    assert '"cancelledJobs": 2' in result.output


def test_endpoint_cancel_commands_call_exact_control_routes_with_yes():
    sdk = _sdk()
    runner = CliRunner()

    session = runner.invoke(
        agent,
        ['endpoint', 'cancel-session', 'conversation-1', '--yes'],
        obj=sdk,
    )
    task = runner.invoke(
        agent,
        ['endpoint', 'cancel-task', 'endpoint-1', 'task-1', '--yes'],
        obj=sdk,
    )
    operation = runner.invoke(
        agent,
        [
            'endpoint', 'cancel-operation', 'session-1', 'operation-1',
            '--yes',
        ],
        obj=sdk,
    )

    assert session.exit_code == 0, session.output
    assert task.exit_code == 0, task.output
    assert operation.exit_code == 0, operation.output
    assert ('cancel-session', 'conversation-1') in sdk.endpoint_executions.calls
    assert ('cancel-task', 'endpoint-1', 'task-1') in sdk.endpoint_executions.calls
    assert ('cancel-operation', 'session-1', 'operation-1') in sdk.endpoint_executions.calls
