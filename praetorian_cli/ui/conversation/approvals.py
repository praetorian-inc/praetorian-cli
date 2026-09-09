import sys
from dataclasses import dataclass


APPROVAL_POLL_INTERVAL_SECONDS = 5


class ApprovalContextError(ValueError):
    """Raised when an approval lacks complete server-authored context."""


@dataclass(frozen=True)
class EndpointApprovalContext:
    action: str
    target_display_name: str
    target_identifier: str
    endpoint_display_name: str
    endpoint_id: str
    capability_families: tuple[str, ...]
    tool_families: tuple[str, ...]
    expected_internal_reach: str
    session_lifetime: str
    impact_class: str
    endpoint_task_id: str = ''
    endpoint_session_id: str = ''
    endpoint_operation_id: str = ''

    @property
    def audit_identifiers(self):
        identifiers = (
            ('Endpoint task', self.endpoint_task_id),
            ('Endpoint session', self.endpoint_session_id),
            ('Endpoint operation', self.endpoint_operation_id),
        )
        return tuple(item for item in identifiers if item[1])


def parse_endpoint_approval(interaction) -> EndpointApprovalContext:
    """Parse the server-authored context required to allow endpoint work."""
    if not isinstance(interaction, dict) or interaction.get('kind') != 'approval':
        raise ApprovalContextError('interaction is not an approval')
    if interaction.get('status') != 'pending':
        raise ApprovalContextError('approval is not pending')

    context = interaction.get('approvalContext')
    if not isinstance(context, dict):
        raise ApprovalContextError('server-authored approvalContext is missing')
    target = _required_object(context, 'target')
    endpoint = _required_object(context, 'endpoint')
    audit_identifiers = _required_object(context, 'auditIdentifiers')

    parsed = EndpointApprovalContext(
        action=_required_text(context, 'action'),
        target_display_name=_required_text(target, 'displayName', 'target'),
        target_identifier=_optional_text(target, 'identifier'),
        endpoint_display_name=_required_text(
            endpoint, 'displayName', 'endpoint'
        ),
        endpoint_id=_required_text(endpoint, 'endpointId', 'endpoint'),
        capability_families=_text_list(context, 'capabilityFamilies'),
        tool_families=_text_list(context, 'toolFamilies'),
        expected_internal_reach=_required_text(
            context, 'expectedInternalReach'
        ),
        session_lifetime=_required_text(context, 'sessionLifetime'),
        impact_class=_required_text(context, 'impactClass'),
        endpoint_task_id=_optional_text(audit_identifiers, 'endpointTaskId'),
        endpoint_session_id=_optional_text(
            audit_identifiers, 'endpointSessionId'
        ),
        endpoint_operation_id=_optional_text(
            audit_identifiers, 'endpointOperationId'
        ),
    )
    if not parsed.capability_families and not parsed.tool_families:
        raise ApprovalContextError(
            'approvalContext has no capability or tool families'
        )
    if not parsed.audit_identifiers:
        raise ApprovalContextError(
            'approvalContext has no endpoint task, session, or operation identifier'
        )
    return parsed


def format_endpoint_approval(context: EndpointApprovalContext) -> str:
    capabilities = ', '.join(context.capability_families) or 'none'
    tools = ', '.join(context.tool_families) or 'none'
    target = context.target_display_name
    if context.target_identifier:
        target = f'{target} ({context.target_identifier})'
    lines = [
        'Aegis endpoint approval required',
        f'Action: {context.action}',
        f'Target: {target}',
        f'Endpoint: {context.endpoint_display_name} ({context.endpoint_id})',
        f'Capability families: {capabilities}',
        f'Tool families: {tools}',
        f'Expected internal reach: {context.expected_internal_reach}',
        f'Session lifetime: {context.session_lifetime}',
        f'Impact class: {context.impact_class}',
    ]
    lines.extend(f'{label}: {value}' for label, value in context.audit_identifiers)
    return '\n'.join(lines)


def prompt_endpoint_approval(
    sdk,
    interaction,
    *,
    echo=print,
    confirm=None,
    interactive=None,
):
    """Review and answer one approval without trusting model-authored text."""
    if interactive is None:
        interactive = sys.stdin.isatty() and sys.stderr.isatty()
    request_id = _optional_text(interaction, 'requestId') if isinstance(interaction, dict) else ''
    if not interactive:
        raise RuntimeError(
            f'endpoint approval {request_id or "unknown"} requires an interactive terminal'
        )
    if confirm is None:
        raise ValueError('confirmation callback is required')

    try:
        context = parse_endpoint_approval(interaction)
    except ApprovalContextError as exc:
        echo(f'Cannot safely allow endpoint work: {exc}')
        if not confirm('Deny this incomplete endpoint approval?', default=True):
            raise RuntimeError(
                f'endpoint approval {request_id or "unknown"} remains pending'
            )
        allow = False
    else:
        echo(format_endpoint_approval(context))
        allow = confirm('Allow this endpoint action?', default=False)

    response = 'true' if allow else 'false'
    return _answer_interaction(sdk, interaction, response, echo)


def _answer_interaction(sdk, interaction, response, echo):
    conversation_id = interaction.get('conversationId')
    request_id = interaction.get('requestId')
    try:
        return sdk.conversations.answer_interaction(
            conversation_id, request_id, response
        )
    except Exception:
        current = sdk.conversations.list_interactions(conversation_id)
        matching = [row for row in current if row.get('requestId') == request_id]
        if matching and matching[0].get('status') != 'pending':
            echo(
                f'Endpoint approval {request_id} is already '
                f'{matching[0].get("status")}.'
            )
            return {'status': matching[0].get('status')}
        raise


def _required_object(values, key):
    value = values.get(key) if isinstance(values, dict) else None
    if not isinstance(value, dict):
        raise ApprovalContextError(f'approvalContext.{key} is required')
    return value


def _required_text(values, key, parent=None):
    value = _optional_text(values, key)
    if not value:
        field = f'{parent}.{key}' if parent else key
        raise ApprovalContextError(f'approvalContext.{field} is required')
    return value


def _optional_text(values, key):
    value = values.get(key) if isinstance(values, dict) else None
    if not isinstance(value, str):
        return ''
    return _safe_display(value)


def _text_list(values, key):
    items = values.get(key) if isinstance(values, dict) else None
    if not isinstance(items, list):
        raise ApprovalContextError(f'approvalContext.{key} must be a list')
    normalized = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ApprovalContextError(
                f'approvalContext.{key} contains an invalid value'
            )
        normalized.append(_safe_display(item, limit=128))
    return tuple(normalized)


def _safe_display(value, limit=500):
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in value
    )
    return ' '.join(printable.split())[:limit]
