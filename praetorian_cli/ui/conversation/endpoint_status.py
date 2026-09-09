from praetorian_cli.sdk.entities.endpoint_executions import (
    endpoint_status_fingerprint,
)


ENDPOINT_STATUS_POLL_INTERVAL_SECONDS = 3


TASK_PHASE_LABELS = {
    'waiting_for_endpoint': 'Waiting for assigned endpoint',
    'claimed': 'Endpoint task claimed',
    'running': 'Running on endpoint',
    'uploaded': 'Endpoint results uploaded',
    'finalizing': 'Finalizing endpoint results',
    'finalized': 'Endpoint task complete',
    'cancel_requested': 'Cancelling endpoint task',
    'cancelled': 'Endpoint task cancelled',
    'failed': 'Endpoint task failed',
}

SESSION_PHASE_LABELS = {
    'starting_sandbox': 'Starting endpoint sandbox',
    'ready': 'Endpoint session ready',
    'executing_tool': 'Executing endpoint tool',
    'reconnecting': 'Endpoint session reconnecting',
    'closing': 'Closing endpoint session',
    'closed': 'Endpoint session closed',
    'cancelled': 'Endpoint session cancelled',
    'expired': 'Endpoint session expired',
    'failed': 'Endpoint session failed',
}


def format_endpoint_execution_status(snapshot):
    """Render Guard's bounded endpoint status projection without output tails."""
    lines = []
    for session in snapshot.get('sessions', []):
        lines.extend(_session_lines(session))
    for task in snapshot.get('tasks', []):
        lines.extend(_task_lines(task))
    return '\n'.join(lines)


def format_endpoint_operation_status(operation):
    """Render safe operation metadata while intentionally omitting output tails."""
    lines = [
        f'Endpoint operation {_safe(operation.get("operationId"))}',
        f'  Sequence: {operation.get("sequence", 0)}',
        f'  Tool: {_safe(operation.get("tool"))}',
        f'  State: {_safe(operation.get("state"))}',
        f'  Updated: {_safe(operation.get("updatedAt"))}',
    ]
    if operation.get('exitCode') is not None:
        lines.append(f'  Exit code: {operation.get("exitCode")}')
    if operation.get('failureCode'):
        lines.append(f'  Failure: {_safe(operation.get("failureCode"))}')
    for artifact in operation.get('artifacts', []):
        lines.append(
            f'  Artifact {_safe(artifact.get("name"))}: '
            f'{artifact.get("sizeBytes", 0)} bytes; '
            f'SHA-256 {_safe(artifact.get("sha256"))}; '
            f'ID {_safe(artifact.get("artifactId"))}'
        )
    return '\n'.join(lines)


def _session_lines(session):
    phase = _safe(session.get('phase'))
    label = SESSION_PHASE_LABELS.get(phase, 'Endpoint session status unknown')
    lines = [
        f'{label}: endpoint {_safe(session.get("endpointId"))}',
        f'  Session: {_safe(session.get("sessionId"))}',
        f'  Bootstrap task: {_safe(session.get("taskId"))}',
        f'  State: {_safe(session.get("state"))}; phase: {phase}',
        f'  Connection: {_safe((session.get("connection") or {}).get("state"))}',
        f'  Sandbox health: {_safe((session.get("sandbox") or {}).get("health"))}',
        f'  Operations: {session.get("activeOperationCount", 0)} active / '
        f'{session.get("operationCount", 0)} total',
    ]
    if session.get('workflowRunId'):
        lines.append(f'  Workflow: {_safe(session.get("workflowRunId"))}')
    if session.get('failureCode'):
        lines.append(f'  Failure: {_safe(session.get("failureCode"))}')
    for operation in session.get('activeOperations', []):
        line = (
            f'  Operation {_safe(operation.get("operationId"))}: '
            f'{_safe(operation.get("tool"))} · {_safe(operation.get("state"))}'
        )
        if operation.get('failureCode'):
            line += f' · failure {_safe(operation.get("failureCode"))}'
        lines.append(line)
    return lines


def _task_lines(task):
    phase = _safe(task.get('phase'))
    connection = _safe(task.get('endpointConnectionState'))
    label = TASK_PHASE_LABELS.get(phase, 'Endpoint task status unknown')
    if phase == 'waiting_for_endpoint' and connection != 'online':
        label = 'Waiting for assigned endpoint (no compute fallback)'
    lines = [
        f'{label}: {_safe(task.get("capability"))} · {_safe(task.get("target"))}',
        f'  Endpoint: {_safe(task.get("endpointId"))}',
        f'  Task: {_safe(task.get("taskId"))}',
        f'  Job: {_safe(task.get("jobKey"))}',
        f'  State: {_safe(task.get("state"))}; phase: {phase}; connection: {connection}',
    ]
    if task.get('failureCode'):
        lines.append(f'  Failure: {_safe(task.get("failureCode"))}')
    artifact = task.get('artifact') or {}
    if artifact:
        lines.append(
            f'  Artifact: version {_safe(artifact.get("versionId"))}; '
            f'SHA-256 {_safe(artifact.get("sha256"))}'
        )
    return lines


def _safe(value, limit=2048):
    if value is None:
        return ''
    value = str(value)
    value = ''.join(character if character.isprintable() else ' ' for character in value)
    return ' '.join(value.split())[:limit]
