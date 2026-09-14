from datetime import datetime

from rich import box
from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


ROLE_PRESENTATION = {
    'user': ('YOU', 'cyan', '▶'),
    'chariot': ('HANNIBAL', 'magenta', '◆'),
    'agent': ('AGENT', 'magenta', '◆'),
    'planner-output': ('PLANNER', 'blue', '◇'),
    'system': ('SYSTEM', 'yellow', '•'),
}


def select_hunt_conversation(records, requested_id=None, require_active=False):
    """Select an active or recent Hunt conversation from authorized records."""
    conversations = _sorted_conversations(records)
    if not conversations:
        raise ValueError('this Hunt has no conversations yet')

    if requested_id is not None:
        requested_id = requested_id.strip().removeprefix('#conversation#')
        if not requested_id:
            raise ValueError('conversation ID is required')
        matches = [
            conversation for conversation in conversations
            if _conversation_id(conversation).startswith(requested_id)
        ]
        exact = next(
            (
                conversation for conversation in matches
                if _conversation_id(conversation) == requested_id
            ),
            None,
        )
        if exact is not None:
            selected = exact
        elif len(matches) == 1:
            selected = matches[0]
        elif len(matches) > 1:
            raise ValueError(
                f'conversation prefix {requested_id!r} is ambiguous'
            )
        else:
            raise ValueError(
                f'conversation {requested_id!r} does not belong to this Hunt'
            )
    else:
        roots = [conversation for conversation in conversations if _is_root(conversation)]
        candidates = roots or conversations
        selected = next(
            (
                conversation for conversation in candidates
                if conversation.get('status') == 'active'
            ),
            candidates[0],
        )

    if require_active:
        if selected.get('status') != 'active':
            raise ValueError('guidance can only be sent to the active Hunt iteration')
        if not _is_root(selected):
            raise ValueError('guidance can only be sent to the root Hunt iteration')
    return selected


def build_hunt_chat(conversations, selected, transcript, max_messages=50):
    """Build a visual Hunt transcript and conversation navigator."""
    selected_id = _conversation_id(selected)
    messages = transcript.get('messages', []) if isinstance(transcript, dict) else []
    messages = [message for message in messages if isinstance(message, dict)]
    omitted = max(0, len(messages) - max_messages)
    messages = messages[-max_messages:]

    header = _chat_header(selected, len(messages), omitted)
    navigator = _conversation_table(conversations, selected_id)
    transcript_view = _transcript_group(messages, omitted)
    return Group(header, Text(''), navigator, Text(''), transcript_view)


def _chat_header(selected, message_count, omitted):
    status = _safe(selected.get('status') or 'unknown', 32)
    active = status == 'active'
    status_style = 'yellow' if active else 'dim'
    status_symbol = '●' if active else '○'
    body = Text()
    body.append(f'{status_symbol} {status.upper()}', style=f'bold {status_style}')
    body.append('   ')
    body.append(f'{message_count} visible messages', style='white')
    if omitted:
        body.append(f'   {omitted} older hidden', style='dim')
    if active:
        body.append('\nGuidance is queued for the next tool turn.', style='green')
    else:
        body.append('\nRead-only: select the active iteration to send guidance.', style='dim')
    return Panel(
        body,
        title=Text('◈  Hannibal Hunt Chat  ◈', style='bold magenta'),
        subtitle=Text(_conversation_id(selected), style='dim'),
        border_style='magenta' if active else 'bright_black',
        box=box.HEAVY,
        padding=(1, 2),
    )


def _conversation_table(records, selected_id):
    conversations = _ordered_conversations(records)
    by_id = {_conversation_id(item): item for item in conversations}
    table = Table(
        title=Text('Conversations', style='bold cyan'),
        box=box.ROUNDED,
        expand=True,
        border_style='cyan',
        show_edge=True,
        padding=(0, 1),
    )
    table.add_column('', width=2, no_wrap=True)
    table.add_column('ITERATION / AGENT', min_width=20, ratio=2)
    table.add_column('STATUS', width=10, no_wrap=True)
    table.add_column('ID', width=10, no_wrap=True)
    table.add_column('STARTED', width=18, no_wrap=True)

    for conversation in conversations:
        conversation_id = _conversation_id(conversation)
        depth = _conversation_depth(conversation, by_id)
        title = _conversation_title(conversation, depth)
        marker = Text('▶', style='bold cyan') if conversation_id == selected_id else Text(' ')
        status = _safe(conversation.get('status') or 'unknown', 32)
        status_style = 'yellow' if status == 'active' else 'dim'
        table.add_row(
            marker,
            Text(f'{"  " * depth}{"↳ " if depth else ""}{title}'),
            Text(status.upper(), style=status_style),
            Text(conversation_id[:8], style='cyan'),
            Text(_format_timestamp(conversation.get('created')), style='dim'),
        )
    return table


def _transcript_group(messages, omitted):
    renderables = []
    if omitted:
        renderables.append(
            Align.center(Text(f'… {omitted} older messages omitted …', style='dim'))
        )
    if not messages:
        renderables.append(
            Panel(
                Text('No messages yet.', style='dim'),
                title='Transcript',
                border_style='dim',
            )
        )
        return Group(*renderables)

    for message in messages:
        renderable = _message_renderable(message)
        if renderable is not None:
            renderables.append(renderable)
    return Group(*renderables)


def _message_renderable(message):
    role = message.get('role') or 'unknown'
    if role == 'tool call':
        return _tool_renderable(message)
    if role == 'tool response':
        return None

    label, style, symbol = ROLE_PRESENTATION.get(
        role,
        (role.upper(), 'white', '•'),
    )
    content = _safe(message.get('content'), 4000) or '—'
    timestamp = _format_timestamp(message.get('timestamp'))
    return Panel(
        Text(content),
        title=Text(f'{symbol} {label}', style=f'bold {style}'),
        subtitle=Text(timestamp, style='dim'),
        border_style=style,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _tool_renderable(message):
    tool = message.get('tool') if isinstance(message.get('tool'), dict) else {}
    name = _safe(tool.get('name') or 'tool', 80)
    completed = tool.get('response') is not None
    symbol = '✓' if completed else '◷'
    style = 'green' if completed else 'yellow'
    state = 'COMPLETED' if completed else 'RUNNING'
    text = Text()
    text.append(f'{symbol} {name}', style=f'bold {style}')
    text.append(f'   {state}', style=style)
    target = _tool_target(tool.get('input'))
    if target:
        text.append(f'\nTarget: {target}', style='dim')
    return Panel(
        text,
        title=Text('⚙ TOOL ACTIVITY', style='bold bright_black'),
        border_style=style,
        box=box.SQUARE,
        padding=(0, 1),
    )


def _tool_target(value):
    if not isinstance(value, dict):
        return ''
    for key in ('target', 'key', 'name', 'capability'):
        if value.get(key):
            return _safe(value[key], 160)
    return ''


def _sorted_conversations(records):
    return sorted(
        (record for record in records or [] if isinstance(record, dict)),
        key=lambda record: _timestamp_sort_key(record.get('created')),
        reverse=True,
    )


def _ordered_conversations(records):
    conversations = _sorted_conversations(records)
    by_parent = {}
    known_ids = {_conversation_id(item) for item in conversations}
    roots = []
    for conversation in conversations:
        parent_id = conversation.get('parent_id')
        if parent_id in known_ids:
            by_parent.setdefault(parent_id, []).append(conversation)
        else:
            roots.append(conversation)

    ordered = []

    def append_family(conversation, seen):
        conversation_id = _conversation_id(conversation)
        if conversation_id in seen:
            return
        seen.add(conversation_id)
        ordered.append(conversation)
        for child in by_parent.get(conversation_id, []):
            append_family(child, seen)

    seen = set()
    for root in roots:
        append_family(root, seen)
    for conversation in conversations:
        append_family(conversation, seen)
    return ordered


def _conversation_id(conversation):
    identifier = (
        conversation.get('uuid')
        or conversation.get('id')
        or conversation.get('key')
        or ''
    )
    return _safe(identifier, 100).removeprefix('#conversation#')


def _conversation_title(conversation, depth):
    if depth:
        title = _safe(
            conversation.get('title') or conversation.get('topic'),
            80,
        )
        return title.removeprefix('Subagent: ') or _conversation_id(conversation)[:8]
    return f'Iteration {_conversation_id(conversation)[:8]}'


def _conversation_depth(conversation, by_id, max_depth=8):
    depth = 0
    parent_id = conversation.get('parent_id')
    seen = set()
    while parent_id and parent_id != 'self' and parent_id in by_id:
        if parent_id in seen or depth >= max_depth:
            break
        seen.add(parent_id)
        depth += 1
        parent_id = by_id[parent_id].get('parent_id')
    return depth


def _is_root(conversation):
    return conversation.get('parent_id') in (None, '', 'self')


def _format_timestamp(value):
    parsed = _timestamp_value(value)
    if parsed is None:
        return '—'
    return parsed.strftime('%Y-%m-%d %H:%M UTC')


def _timestamp_sort_key(value):
    parsed = _timestamp_value(value)
    return parsed.timestamp() if parsed is not None else float('-inf')


def _timestamp_value(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _safe(value, limit):
    if value is None:
        return ''
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in str(value)
    )
    return ' '.join(printable.split())[:limit]
