import getpass
import sys
from dataclasses import dataclass


APPROVAL_POLL_INTERVAL_SECONDS = 5
MAX_CREDENTIAL_INTERACTION_FIELDS = 12


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


def prompt_ephemeral_credentials(
    sdk,
    interaction,
    *,
    echo=print,
    prompt=None,
    interactive=None,
):
    """Collect a credential response through the ephemeral secret broker.

    Plaintext values exist only in the local prompt result and the broker add
    request. The durable interaction receives only the broker's opaque secret
    reference. If recording that reference fails, the secret is deleted on a
    best-effort basis so it cannot be orphaned.
    """
    if (
        not isinstance(interaction, dict)
        or interaction.get('kind') != 'credential'
    ):
        raise ValueError('interaction is not a credential request')
    if interaction.get('status') != 'pending':
        raise ValueError('credential request is not pending')

    conversation_id = _optional_text(interaction, 'conversationId')
    request_id = _optional_text(interaction, 'requestId')
    if not conversation_id:
        raise ValueError('credential request conversation ID is required')
    if not request_id:
        raise ValueError('credential request ID is required')

    if interactive is None:
        interactive = sys.stdin.isatty() and sys.stderr.isatty()
    if not interactive:
        raise RuntimeError(
            f'credential request {request_id} requires an interactive terminal'
        )
    if prompt is None:
        def prompt(field):
            return getpass.getpass(f'{field}: ')

    fields = normalize_credential_interaction_fields(interaction.get('fields'))
    echo(
        f'Credential input required for request {request_id}. '
        'Values are sent once to the secret broker and are never stored in chat.'
    )
    parameters = {}
    try:
        for field in fields:
            value = prompt(field)
            if not isinstance(value, str):
                raise ValueError(
                    f'a value for credential field {field!r} is required'
                )
            if not value:
                if credential_field_is_optional(field):
                    continue
                raise ValueError(
                    f'a value for credential field {field!r} is required'
                )
            parameters[field] = value

        return submit_ephemeral_credentials(
            sdk,
            interaction,
            parameters,
            echo=echo,
        )
    finally:
        # Drop references promptly. Python strings cannot be zeroized, but the
        # values never enter output, logs, messages, events, or argv.
        parameters.clear()


def submit_ephemeral_credentials(sdk, interaction, parameters, *, echo=print):
    """Store collected values ephemerally and answer with only their reference."""
    if (
        not isinstance(interaction, dict)
        or interaction.get('kind') != 'credential'
        or interaction.get('status') != 'pending'
    ):
        raise ValueError('credential request is not pending')
    conversation_id = _optional_text(interaction, 'conversationId')
    request_id = _optional_text(interaction, 'requestId')
    if not conversation_id:
        raise ValueError('credential request conversation ID is required')
    if not request_id:
        raise ValueError('credential request ID is required')
    if (
        not isinstance(parameters, dict)
        or not parameters
        or any(
            not isinstance(name, str)
            or not name
            or not isinstance(value, str)
            or not value
            for name, value in parameters.items()
        )
    ):
        raise ValueError('credential values are required')

    try:
        broker_response = sdk.credentials.add_ephemeral(parameters)
    except Exception:
        raise RuntimeError(
            'Unable to store credentials securely; the interaction '
            'remains pending.'
        ) from None

    credential_values = (
        broker_response.get('credentialValue')
        if isinstance(broker_response, dict)
        else None
    )
    secret_ref = (
        credential_values.get('credential_id')
        if isinstance(credential_values, dict)
        else None
    )
    if not isinstance(secret_ref, str) or not secret_ref.strip():
        raise RuntimeError(
            'The secret broker did not return a credential reference; '
            'the interaction remains pending.'
        )
    secret_ref = secret_ref.strip()

    try:
        return sdk.conversations.answer_interaction(
            conversation_id,
            request_id,
            secret_ref,
        )
    except Exception:
        try:
            sdk.credentials.delete_ephemeral(secret_ref)
        except Exception:
            pass
        terminal_status = _interaction_terminal_status(
            sdk,
            conversation_id,
            request_id,
        )
        if terminal_status:
            echo(f'Credential request {request_id} was resolved elsewhere.')
            return {'status': terminal_status}
        raise RuntimeError(
            'Unable to send the credential reference; the temporary secret '
            'was cleaned up and the interaction remains pending.'
        ) from None


def normalize_credential_interaction_fields(fields):
    """Normalize and bound untrusted agent-authored credential field names."""
    if not isinstance(fields, list):
        return ('input',)
    normalized = []
    seen = set()
    for value in fields:
        if not isinstance(value, str):
            continue
        field = value.strip()
        if (
            not field
            or len(field) > 128
            or any(not character.isprintable() for character in field)
        ):
            continue
        identity = field.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(field)
        if len(normalized) >= MAX_CREDENTIAL_INTERACTION_FIELDS:
            break
    return tuple(normalized or ('input',))


def credential_field_is_optional(field):
    normalized = field.strip().casefold()
    return normalized in {
        'totp', 'totp_secret', 'totp_seed', 'totp_code',
        'otp', 'otp_code', 'mfa', 'mfa_code', '2fa',
    }


def _interaction_terminal_status(sdk, conversation_id, request_id):
    try:
        current = sdk.conversations.list_interactions(conversation_id)
    except Exception:
        return ''
    return next(
        (
            row.get('status') for row in current
            if isinstance(row, dict)
            and row.get('requestId') == request_id
            and row.get('status') in ('answered', 'expired')
        ),
        '',
    )


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
