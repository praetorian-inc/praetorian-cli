from datetime import datetime

from rich import box
from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from praetorian_cli.ui.conversation.approvals import (
    ApprovalContextError,
    parse_endpoint_approval,
    prompt_endpoint_approval,
    prompt_ephemeral_credentials,
    normalize_credential_interaction_fields,
)


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


def build_hunt_chat(
    conversations,
    selected,
    transcript,
    max_messages=50,
    pending_interactions=None,
):
    """Build a visual Hunt transcript and conversation navigator."""
    selected_id = _conversation_id(selected)
    messages = transcript.get('messages', []) if isinstance(transcript, dict) else []
    messages = [message for message in messages if isinstance(message, dict)]
    omitted = max(0, len(messages) - max_messages)
    messages = messages[-max_messages:]

    header = _chat_header(selected, len(messages), omitted)
    navigator = _conversation_table(conversations, selected_id)
    transcript_view = _transcript_group(messages, omitted)
    renderables = [header, Text(''), navigator]
    pending = [
        interaction for interaction in pending_interactions or []
        if isinstance(interaction, dict)
        and interaction.get('status') == 'pending'
    ]
    if pending:
        renderables.extend([
            Text(''),
            build_hunt_interactions(
                pending,
                title='Pending operator interactions',
            ),
        ])
    renderables.extend([Text(''), transcript_view])
    return Group(*renderables)


def hunt_interaction_key(interaction):
    """Return a stable, non-secret identity for a durable interaction."""
    if not isinstance(interaction, dict):
        return ('', '')
    key = interaction.get('key')
    if isinstance(key, str) and key:
        return ('key', key)
    return (
        _safe(interaction.get('conversationId'), 100),
        _safe(interaction.get('requestId'), 100),
    )


def build_hunt_interactions(interactions, title='Pending Hunt interactions'):
    """Render safe interaction metadata without model text or secret values."""
    rows = [row for row in interactions or [] if isinstance(row, dict)]
    table = Table(
        title=Text(title, style='bold yellow'),
        box=box.ROUNDED,
        expand=True,
        border_style='yellow',
        show_edge=True,
        padding=(0, 1),
    )
    table.add_column('KIND', width=12, no_wrap=True)
    table.add_column('CONVERSATION', width=12, no_wrap=True)
    table.add_column('REQUEST', width=12, no_wrap=True)
    table.add_column('SAFE CONTEXT', ratio=3)
    if not rows:
        table.add_row('—', '—', '—', 'No pending operator interactions.')
        return table

    for interaction in rows:
        kind = _safe(interaction.get('kind') or 'unknown', 32)
        conversation_id = _safe(interaction.get('conversationId'), 100)
        request_id = _safe(interaction.get('requestId'), 100)
        table.add_row(
            Text(kind.upper(), style='yellow'),
            Text(conversation_id[:12] or '—', style='cyan'),
            Text(request_id[:12] or '—', style='cyan'),
            Text(_safe_interaction_context(interaction)),
        )
    return table


def review_pending_hunt_interactions(
    sdk,
    interactions,
    console,
    *,
    confirm,
    credential_prompt,
    handled=None,
    interactive=True,
):
    """Securely answer supported pending Hunt interactions once per watcher."""
    handled = handled if handled is not None else set()
    if not interactive:
        return handled

    for interaction in interactions or []:
        if not isinstance(interaction, dict):
            continue
        kind = interaction.get('kind')
        if kind not in ('approval', 'credential'):
            continue
        identity = hunt_interaction_key(interaction)
        if identity in handled:
            continue
        handled.add(identity)
        console.print()
        try:
            if kind == 'approval':
                prompt_endpoint_approval(
                    sdk,
                    interaction,
                    echo=lambda message: _console_print_plain(console, message),
                    confirm=confirm,
                    interactive=True,
                )
            else:
                prompt_ephemeral_credentials(
                    sdk,
                    interaction,
                    echo=lambda message: _console_print_plain(console, message),
                    prompt=credential_prompt,
                    interactive=True,
                )
        except Exception:
            request_id = _safe(interaction.get('requestId'), 100) or 'unknown'
            _console_print_plain(
                console,
                f'Unable to answer {kind} interaction {request_id}; '
                'it remains pending.',
            )
    return handled


def _console_print_plain(console, message):
    try:
        console.print(message, markup=False)
    except TypeError:
        console.print(message)


def _safe_interaction_context(interaction):
    kind = interaction.get('kind')
    if kind == 'approval':
        try:
            context = parse_endpoint_approval(interaction)
        except ApprovalContextError:
            return 'Endpoint approval has incomplete server-authored context; deny only.'
        target = context.target_display_name
        endpoint = context.endpoint_display_name
        return _safe(f'{context.action} · {target} · endpoint {endpoint}', 240)
    if kind == 'credential':
        fields = ', '.join(
            normalize_credential_interaction_fields(interaction.get('fields'))
        )
        return _safe(
            f'Secure one-time credential input requested: {fields}',
            240,
        )
    return 'Unsupported interaction kind; no response will be sent.'


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
    body = [Text(content)]
    attachment_lines = safe_hunt_attachment_metadata(message)
    if attachment_lines:
        attachments = Text('\n')
        attachments.append('\n'.join(attachment_lines), style='dim cyan')
        body.append(attachments)
    timestamp = _format_timestamp(message.get('timestamp'))
    return Panel(
        Group(*body),
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
    attachments = safe_hunt_attachment_metadata(tool)
    if attachments:
        text.append(f'\n{" · ".join(attachments)}', style='dim cyan')
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


def safe_hunt_attachment_metadata(message, max_items=12):
    """Return bounded attachment labels without paths, URLs, or payload data."""
    if not isinstance(message, dict):
        return ()

    candidates = []
    for field, default_kind in (
        ('attachments', 'attachment'),
        ('attachment', 'attachment'),
        ('screenshots', 'screenshot'),
        ('screenshot', 'screenshot'),
    ):
        value = message.get(field)
        if isinstance(value, list):
            candidates.extend((item, default_kind) for item in value)
        elif value is not None:
            candidates.append((value, default_kind))

    rendered = []
    for value, default_kind in candidates[:max_items]:
        if isinstance(value, str):
            name = _safe_attachment_name(value)
            rendered.append(f'▣ {default_kind.title()}: {name or "unnamed"}')
            continue
        if not isinstance(value, dict):
            continue

        media_type = _safe(
            value.get('mediaType')
            or value.get('contentType')
            or value.get('mimeType')
            or value.get('type'),
            80,
        )
        kind = 'screenshot' if (
            default_kind == 'screenshot'
            or media_type.lower().startswith('image/')
        ) else default_kind
        name = _safe_attachment_name(
            value.get('displayName')
            or value.get('filename')
            or value.get('name')
            or value.get('title')
        )
        details = []
        if media_type:
            details.append(media_type)
        size = value.get('bytes') if value.get('bytes') is not None else value.get('size')
        if isinstance(size, int) and 0 <= size <= 10 ** 12:
            details.append(f'{size} bytes')
        width = value.get('width')
        height = value.get('height')
        if (
            isinstance(width, int)
            and isinstance(height, int)
            and 0 < width <= 100000
            and 0 < height <= 100000
        ):
            details.append(f'{width}×{height}')
        label = f'▣ {kind.title()}: {name or "unnamed"}'
        if details:
            label += f' ({", ".join(details)})'
        rendered.append(label)
    return tuple(rendered)


def _safe_attachment_name(value):
    name = _safe(value, 160).replace('\\', '/')
    return name.rsplit('/', 1)[-1]


def ordered_hunt_conversations(records):
    """Return roots and descendants in stable navigator order."""
    return _ordered_conversations(records)


def hunt_conversation_id(conversation):
    """Return a normalized Hunt conversation identifier."""
    return _conversation_id(conversation)


def hunt_conversation_is_root(conversation):
    """Return whether a Hunt conversation is a root iteration."""
    return _is_root(conversation)


def hunt_conversation_depth(conversation, records):
    """Return bounded descendant depth for a conversation navigator."""
    by_id = {_conversation_id(item): item for item in records or []}
    return _conversation_depth(conversation, by_id)


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
