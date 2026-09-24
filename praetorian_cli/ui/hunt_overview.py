import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from praetorian_cli.ui.hunt_format import (
    record_value as _value,
    safe_text as _bounded_value,
)


UNAVAILABLE = '—'
TERMINAL_HUNT_STATUSES = frozenset({
    'completed',
    'errored',
    'expired',
    'stopped',
})
MAX_SCOPE_ITEMS = 5
MAX_SCOPE_ITEM_LENGTH = 72
MAX_SCOPE_SUMMARY_LENGTH = 400
MAX_AGENT_ITEMS = 5
MAX_AGENT_ITEM_LENGTH = 80
MAX_AGENT_SUMMARY_LENGTH = 450

_SEVERITY_PRIORITY = {
    'critical': 0,
    'high': 10,
    'medium': 20,
    'low': 30,
    'info': 40,
    'exposure': 50,
}
_SEVERITY_CODES = {
    'C': 'critical',
    'H': 'high',
    'M': 'medium',
    'L': 'low',
    'I': 'info',
    'E': 'exposure',
}


def format_remaining_time(hunt, now=None):
    """Render the Hunt expiry countdown using the WebUI's status rules."""
    status = str(_value(hunt, 'status') or '').strip().lower()
    if status in TERMINAL_HUNT_STATUSES:
        return UNAVAILABLE

    expires_at = _parse_timestamp(_value(hunt, 'expiresAt', 'expires_at'))
    if expires_at is None:
        return UNAVAILABLE

    current = _coerce_now(now)
    remaining_seconds = (expires_at - current).total_seconds()
    if remaining_seconds <= 0:
        return 'Expired'

    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    if hours:
        return f'{hours}h {minutes}m'
    return f'{minutes}m'


def format_projected_cost(cost_status):
    """Format recorded USD usage, preserving a real zero-dollar result."""
    if not isinstance(cost_status, dict):
        return UNAVAILABLE
    if cost_status.get('currency') != 'USD':
        return UNAVAILABLE

    total = cost_status.get('total')
    if not isinstance(total, dict):
        return UNAVAILABLE

    # This is the same empty-state signal used by the WebUI. A zero cost with
    # positive recorded token usage is real and must remain distinguishable
    # from an old or never-run Hunt with no usage record.
    total_tokens = total.get('total_tokens')
    if isinstance(total_tokens, bool) or not isinstance(total_tokens, (int, float)):
        return UNAVAILABLE
    if total_tokens <= 0:
        return UNAVAILABLE

    cost = total.get('cost')
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        return UNAVAILABLE
    if not math.isfinite(cost) or cost < 0:
        return UNAVAILABLE

    try:
        rounded = Decimal(str(cost)).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, ValueError):
        return UNAVAILABLE
    if rounded == 0:
        rounded = Decimal('0')
    return f'${rounded:,.2f}'


def highest_hunt_severity(findings):
    """Return the highest recognized severity among Hunt-linked risks."""
    highest = None
    highest_priority = math.inf
    for finding in findings or []:
        risk = _risk_record(finding)
        severity = _risk_severity(risk)
        priority = _SEVERITY_PRIORITY.get(severity, math.inf)
        if priority < highest_priority:
            highest = severity
            highest_priority = priority
    return highest


def summarize_hunt_scope(scope, max_items=MAX_SCOPE_ITEMS):
    """Build a readable, item-bounded summary of a Hunt's target scope."""
    if scope is None or scope == [] or scope == ():
        return 'Unrestricted'
    if isinstance(scope, str):
        scope = [scope]
    if not isinstance(scope, (list, tuple)):
        return UNAVAILABLE

    labels = [
        _scope_label(item)
        for item in scope
        if str(item or '').strip()
    ]
    if not labels:
        return 'Unrestricted'
    return _bounded_list_summary(
        labels,
        max_items=max_items,
        item_limit=MAX_SCOPE_ITEM_LENGTH,
        total_limit=MAX_SCOPE_SUMMARY_LENGTH,
    )


def summarize_root_agents(conversations, max_items=MAX_AGENT_ITEMS):
    """Build a bounded summary of root Hunt iteration conversations."""
    if conversations is None:
        return UNAVAILABLE

    # Match the WebUI Agents view: newest roots first, with missing or invalid
    # creation timestamps sorted as epoch values. Python's stable sort keeps
    # the API order for ties.
    roots = sorted(
        (
            conversation
            for conversation in conversations
            if isinstance(conversation, dict)
        ),
        key=_conversation_created_timestamp,
        reverse=True,
    )
    labels = []
    for conversation in roots:
        label = (
            _value(conversation, 'title', 'topic')
            or _iteration_label(conversation)
        )
        labels.append(str(label))
    if not labels:
        return 'None yet'
    return _bounded_list_summary(
        labels,
        max_items=max_items,
        item_limit=MAX_AGENT_ITEM_LENGTH,
        total_limit=MAX_AGENT_SUMMARY_LENGTH,
    )


_NOT_PROVIDED = object()


def build_hunt_overview(
    sdk,
    hunt,
    now=None,
    *,
    cost_status=_NOT_PROVIDED,
    root_agents=_NOT_PROVIDED,
    findings=_NOT_PROVIDED,
):
    """Collect failure-tolerant operational metrics for Hunt status views.

    Callers which already loaded bounded Hunt data may provide it to avoid a
    second set of API reads. Existing status commands retain their historical
    behavior when the keyword-only values are omitted.
    """
    hunt_id = _hunt_id(hunt)

    if cost_status is _NOT_PROVIDED:
        try:
            cost_status = sdk.hunts.get_cost(hunt_id)
        except Exception:
            cost_status = None

    if root_agents is _NOT_PROVIDED:
        root_agents = None
        try:
            root_agents, _ = sdk.hunts.list_root_conversations(hunt_id)
        except Exception:
            pass

    if findings is _NOT_PROVIDED:
        findings = None
        try:
            findings, _ = sdk.hunts.list_findings(hunt_id, pages=100000)
        except Exception:
            pass

    highest_severity = highest_hunt_severity(findings)
    iteration_count = _value(hunt, 'iterationCount', 'iteration_count')
    if iteration_count is None:
        iteration_count = 0

    return {
        'remaining': format_remaining_time(hunt, now=now),
        'projected_cost': format_projected_cost(cost_status),
        'root_agent': _bounded_value(_value(hunt, 'agent'), 80) or UNAVAILABLE,
        'root_agent_count': (
            len(root_agents) if root_agents is not None else UNAVAILABLE
        ),
        'iterations': iteration_count,
        'highest_severity': (
            highest_severity.title() if highest_severity else UNAVAILABLE
        ),
        'scope_summary': summarize_hunt_scope(
            _value(hunt, 'scope'),
        ),
        'agent_summary': summarize_root_agents(root_agents),
    }


def _parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith('Z'):
        normalized = f'{normalized[:-1]}+00:00'
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_now(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    timestamp = float(value)
    # Accept both normal Unix seconds and the millisecond timestamp shape used
    # by the WebUI's computeTimeRemaining helper.
    if abs(timestamp) >= 100_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _risk_record(finding):
    if not isinstance(finding, dict):
        return {}
    risk = finding.get('risk')
    return risk if isinstance(risk, dict) else finding


def _risk_severity(risk):
    # Guard's risk status wire format stores severity in the second character
    # (for example, TC and OH). This deliberately matches getRiskStatusLabel in
    # the WebUI instead of trusting derived labels or a trailing character.
    # Deleted statuses retain severity there and append their deletion reason
    # as a third character (for example, DCF).
    status = str(risk.get('status') or '').strip()
    return _SEVERITY_CODES.get(status[1:2].upper())


def _scope_label(value):
    full = _bounded_value(value, 500)
    if full.startswith('#asset#'):
        full = full[len('#asset#'):]
    if '#' not in full:
        return full

    name, identifier = full.rsplit('#', 1)
    if identifier and identifier != name:
        return f'{name} ({identifier})'
    return name or identifier


def _iteration_label(conversation):
    identifier = _value(conversation, 'uuid', 'id', 'key')
    identifier = str(identifier or '').removeprefix('#conversation#')
    return f'Iteration {identifier[:8]}' if identifier else 'Iteration'


def _conversation_created_timestamp(conversation):
    created = _parse_timestamp(_value(conversation, 'created'))
    return created.timestamp() if created is not None else 0


def _bounded_list_summary(values, max_items, item_limit, total_limit):
    max_items = max(1, int(max_items))
    shown = [
        _bounded_value(value, item_limit)
        for value in values[:max_items]
    ]
    omitted = len(values) - len(shown)
    suffix = f' … (+{omitted} more)' if omitted else ''
    summary = ', '.join(shown)
    available = total_limit - len(suffix)
    if len(summary) > available:
        summary = summary[:max(0, available - 1)].rstrip(' ,') + '…'
    return summary + suffix


def _hunt_id(hunt):
    identifier = _value(hunt, 'uuid', 'id', 'key')
    return str(identifier or '').removeprefix('#hunt#')
