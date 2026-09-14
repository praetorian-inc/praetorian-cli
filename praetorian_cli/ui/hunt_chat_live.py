import asyncio
import copy
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone

from rich import box
from rich.console import Group
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from praetorian_cli.ui.hunt_chat import (
    ROLE_PRESENTATION,
    hunt_conversation_depth,
    hunt_conversation_id,
    hunt_conversation_is_root,
    ordered_hunt_conversations,
    safe_hunt_attachment_metadata,
    select_hunt_conversation,
)


DEFAULT_CHAT_REFRESH_SECONDS = 3.0
MIN_CHAT_REFRESH_SECONDS = 1.0
MAX_CHAT_REFRESH_SECONDS = 30.0
DEFAULT_HISTORY_PAGE_SIZE = 25
MAX_MESSAGE_CHARACTERS = 12000
MAX_TOOL_DETAIL_CHARACTERS = 6000
MAX_TOOL_COLLECTION_ITEMS = 40
MAX_TOOL_OBJECT_DEPTH = 6
_REDACTED = '[redacted]'
_SENSITIVE_FIELD = re.compile(
    r'(?:password|passwd|secret|authorization|cookie|credential|api[_-]?key|'
    r'access[_-]?token|refresh[_-]?token|private[_-]?key)',
    re.IGNORECASE,
)
_ANSI_ESCAPE = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')


def supports_live_hunt_chat(input_stream=None, output_stream=None):
    """Return whether a fullscreen chat can safely own the terminal."""
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    try:
        return input_stream.isatty() and output_stream.isatty()
    except (AttributeError, OSError):
        return False


class HuntChatSession:
    """API-backed state for live chat, independent from the terminal widgets."""

    def __init__(
        self,
        sdk,
        hunt_id,
        *,
        requested_id=None,
        exact_requested_id=False,
        refresh_interval=DEFAULT_CHAT_REFRESH_SECONDS,
        page_size=DEFAULT_HISTORY_PAGE_SIZE,
    ):
        self.sdk = sdk
        self.hunt_id = str(hunt_id or '').strip()
        self.requested_id = requested_id
        self.exact_requested_id = bool(exact_requested_id)
        self.refresh_interval = min(
            max(float(refresh_interval), MIN_CHAT_REFRESH_SECONDS),
            MAX_CHAT_REFRESH_SECONDS,
        )
        self.page_size = max(1, min(int(page_size), 100))
        self.conversations = []
        self.selected = None
        self.transcript = {'messages': []}
        self.pending_interactions = []
        self.history_page = 0
        self.unseen_messages = 0
        self.expanded_tools = set()
        self.error = ''
        self.warning = ''
        self.notice = ''
        self.consecutive_failures = 0
        self.last_refresh = None

    @property
    def selected_id(self):
        return hunt_conversation_id(self.selected or {})

    @property
    def ordered_conversations(self):
        return ordered_hunt_conversations(self.conversations)

    @property
    def messages(self):
        records = (
            self.transcript.get('messages', [])
            if isinstance(self.transcript, dict)
            else []
        )
        return group_hunt_tool_messages(records)

    @property
    def page_count(self):
        return max(1, math.ceil(len(self.messages) / self.page_size))

    @property
    def visible_messages(self):
        messages = self.messages
        page = min(self.history_page, self.page_count - 1)
        end = len(messages) - (page * self.page_size)
        start = max(0, end - self.page_size)
        return messages[start:end]

    @property
    def can_guide(self):
        return bool(
            self.selected
            and self.selected.get('status') == 'active'
            and hunt_conversation_is_root(self.selected)
        )

    @property
    def selected_pending_count(self):
        selected_id = self.selected_id
        return sum(
            1 for row in self.pending_interactions
            if isinstance(row, dict)
            and row.get('status') == 'pending'
            and str(row.get('conversationId') or '') == selected_id
        )

    def refresh(self, *, raise_errors=False):
        """Refresh atomically; retain the last good view after transient errors."""
        try:
            conversations, _ = self.sdk.hunts.list_conversations(self.hunt_id)
            requested = self.selected_id or self.requested_id
            selected = select_hunt_conversation(
                conversations,
                requested_id=requested,
                exact_id=self.exact_requested_id,
            )
            selected_id = hunt_conversation_id(selected)
            transcript = self.sdk.conversations.get(selected_id)
        except Exception as exc:
            self._record_failure(exc)
            if raise_errors:
                raise
            return False

        warning = ''
        try:
            pending = self.sdk.hunts.list_interactions(
                self.hunt_id,
                status='pending',
            )
        except Exception:
            pending = self.pending_interactions
            warning = 'Pending interactions are temporarily unavailable; retrying.'

        old_count = len(self.messages)
        same_selection = selected_id == self.selected_id
        self.conversations = [
            row for row in conversations or [] if isinstance(row, dict)
        ]
        self.selected = selected
        self.transcript = (
            copy.deepcopy(transcript)
            if isinstance(transcript, dict)
            else {'messages': []}
        )
        self.pending_interactions = [
            row for row in pending or []
            if isinstance(row, dict) and row.get('status') == 'pending'
        ]
        if not same_selection:
            self.history_page = 0
            self.unseen_messages = 0
        elif self.history_page:
            self.unseen_messages += max(0, len(self.messages) - old_count)
        else:
            self.unseen_messages = 0
        self.history_page = min(self.history_page, self.page_count - 1)
        self.error = ''
        self.warning = warning
        self.consecutive_failures = 0
        self.last_refresh = datetime.now(timezone.utc)
        return True

    def select_conversation(self, conversation_id):
        """Load an authorized Hunt conversation without losing state on failure."""
        try:
            selected = select_hunt_conversation(
                self.conversations,
                requested_id=conversation_id,
            )
            selected_id = hunt_conversation_id(selected)
            transcript = self.sdk.conversations.get(selected_id)
        except Exception as exc:
            self._record_failure(exc)
            return False

        self.selected = selected
        self.transcript = (
            copy.deepcopy(transcript)
            if isinstance(transcript, dict)
            else {'messages': []}
        )
        self.history_page = 0
        self.unseen_messages = 0
        self.error = ''
        self.notice = ''
        self.consecutive_failures = 0
        return True

    def move_selection(self, delta):
        conversations = self.ordered_conversations
        if not conversations:
            return False
        identifiers = [hunt_conversation_id(row) for row in conversations]
        try:
            index = identifiers.index(self.selected_id)
        except ValueError:
            index = 0
        target = min(max(index + delta, 0), len(conversations) - 1)
        if target == index:
            return True
        return self.select_conversation(identifiers[target])

    def older_history(self):
        if self.history_page + 1 >= self.page_count:
            return False
        self.history_page += 1
        return True

    def newer_history(self):
        if self.history_page == 0:
            return False
        self.history_page -= 1
        if self.history_page == 0:
            self.unseen_messages = 0
        return True

    def send_guidance(self, message):
        """Revalidate active-root authorization immediately before steering."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError('guidance message is required')
        try:
            conversations, _ = self.sdk.hunts.list_conversations(self.hunt_id)
            selected = select_hunt_conversation(
                conversations,
                requested_id=self.selected_id,
                require_active=True,
            )
            result = self.sdk.conversations.send_message(
                hunt_conversation_id(selected),
                message,
            )
        except Exception as exc:
            self._record_failure(exc)
            raise
        self.conversations = [
            row for row in conversations or [] if isinstance(row, dict)
        ]
        self.selected = selected
        self.error = ''
        self.notice = 'Guidance queued for the active root iteration.'
        return result

    def _record_failure(self, exc):
        self.consecutive_failures += 1
        self.error = _terminal_safe_text(str(exc) or exc.__class__.__name__, 300)
        self.warning = ''


class ConversationListItem(ListItem):
    def __init__(self, conversation, records):
        self.conversation_id = hunt_conversation_id(conversation)
        super().__init__(Static(_conversation_label(conversation, records)))


class ToolActivity(Static):
    can_focus = True

    class Toggled(Message):
        def __init__(self, key, expanded):
            self.key = key
            self.expanded = expanded
            super().__init__()

    def __init__(self, message, index, expanded=False):
        self.message_record = message
        self.message_index = index
        self.tool_key = hunt_tool_key(message, index)
        self.expanded = expanded
        super().__init__()

    def render(self):
        return build_live_tool_activity(self.message_record, self.expanded)

    def on_key(self, event):
        if event.key not in ('enter', 'space'):
            return
        self.expanded = not self.expanded
        self.post_message(self.Toggled(self.tool_key, self.expanded))
        self.refresh()
        event.stop()


class HuntChatApp(App):
    """Fullscreen live operator chat for one authorized Hunt."""

    TITLE = 'Hannibal Hunt Chat'
    SUB_TITLE = 'live operator view'
    CSS = """
    Screen { background: #090d18; color: #e8e8ee; }
    #body { height: 1fr; }
    #navigator-pane {
        width: 34%; min-width: 28; max-width: 52;
        border-right: solid #38bdf8; padding: 0 1;
    }
    #navigator-title { height: 3; color: #67e8f9; text-style: bold; padding: 1 0; }
    #conversation-list { height: 1fr; background: #0f172a; }
    #conversation-list > ListItem { padding: 0 1; height: auto; }
    #conversation-list > ListItem.--highlight { background: #23345d; }
    #chat-pane { width: 1fr; padding: 0 1; }
    #chat-status { height: 4; border-bottom: solid #a855f7; padding: 0 1; }
    #transcript { height: 1fr; scrollbar-color: #a855f7; padding: 1 0; }
    #transcript > Static { margin: 0 0 1 0; }
    ToolActivity:focus { border: tall #67e8f9; }
    #interaction-status { height: 2; color: #facc15; padding: 0 1; }
    #composer { dock: bottom; height: 3; border: tall #a855f7; }
    #composer:disabled { border: tall #475569; color: #94a3b8; }
    Footer { background: #111827; }
    """
    BINDINGS = [
        Binding('ctrl+up', 'previous_conversation', 'previous conversation'),
        Binding('ctrl+down', 'next_conversation', 'next conversation'),
        Binding('ctrl+left', 'older_history', 'older history'),
        Binding('ctrl+right', 'newer_history', 'newer history'),
        Binding('ctrl+r', 'force_refresh', 'refresh'),
        Binding('ctrl+i', 'review_interactions', 'interactions'),
        Binding('ctrl+c', 'cancel_chat', 'close'),
        Binding('escape', 'cancel_chat', 'close', show=False),
    ]

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.sub_title = (
            f'Hunt {_terminal_safe_text(session.hunt_id, 48)} · live operator view'
        )
        self._request_lock = asyncio.Lock()
        self._navigator_fingerprint = None
        self._transcript_fingerprint = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='body'):
            with Vertical(id='navigator-pane'):
                yield Static('ROOTS & SUBAGENTS', id='navigator-title')
                yield ListView(id='conversation-list')
            with Vertical(id='chat-pane'):
                yield Static(id='chat-status')
                yield VerticalScroll(id='transcript')
                yield Static(id='interaction-status')
                yield Input(id='composer')
        yield Footer()

    async def on_mount(self):
        await self._render_state(force=True)
        self.set_interval(self.session.refresh_interval, self._poll)
        self.query_one('#composer', Input).focus()

    async def _poll(self):
        if self._request_lock.locked():
            return
        async with self._request_lock:
            await asyncio.to_thread(self.session.refresh)
        await self._render_state()

    async def _load_selected(self, conversation_id):
        if self._request_lock.locked():
            return
        async with self._request_lock:
            await asyncio.to_thread(
                self.session.select_conversation,
                conversation_id,
            )
        await self._render_state(force=True)

    @on(ListView.Selected, '#conversation-list')
    async def _conversation_selected(self, event):
        item = event.item
        if isinstance(item, ConversationListItem):
            await self._load_selected(item.conversation_id)

    @on(Input.Submitted, '#composer')
    async def _guidance_submitted(self, event):
        message = event.value
        if not message.strip():
            return
        if not self.session.can_guide:
            self.session.error = 'Guidance is available only for the active root iteration.'
            await self._render_state()
            return
        composer = self.query_one('#composer', Input)
        composer.disabled = True
        try:
            async with self._request_lock:
                await asyncio.to_thread(self.session.send_guidance, message)
                await asyncio.to_thread(self.session.refresh)
        except Exception:
            pass
        else:
            composer.value = ''
        finally:
            await self._render_state(force=True)

    @on(ToolActivity.Toggled)
    def _tool_toggled(self, event):
        if event.expanded:
            self.session.expanded_tools.add(event.key)
        else:
            self.session.expanded_tools.discard(event.key)

    async def action_previous_conversation(self):
        await self._move_conversation(-1)

    async def action_next_conversation(self):
        await self._move_conversation(1)

    async def _move_conversation(self, delta):
        if self._request_lock.locked():
            return
        async with self._request_lock:
            await asyncio.to_thread(self.session.move_selection, delta)
        await self._render_state(force=True)

    async def action_older_history(self):
        if self.session.older_history():
            await self._render_state(force=True)

    async def action_newer_history(self):
        if self.session.newer_history():
            await self._render_state(force=True)

    async def action_force_refresh(self):
        await self._poll()

    def action_review_interactions(self):
        if self.session.pending_interactions:
            self.exit(result='review-interactions')
        else:
            self.session.notice = 'There are no pending Hunt interactions.'
            self.call_after_refresh(self._render_state)

    def action_cancel_chat(self):
        self.exit(result='cancelled')

    async def _render_state(self, force=False):
        await self._render_navigation(force)
        await self._render_transcript(force)

        selected = self.session.selected or {}
        selected_id = self.session.selected_id or 'unknown'
        status = _terminal_safe_text(selected.get('status') or 'unknown', 32).upper()
        kind = 'ROOT ITERATION' if hunt_conversation_is_root(selected) else 'SUBAGENT'
        page = self.session.history_page + 1
        page_count = self.session.page_count
        chat_status = Text()
        chat_status.append(f'{kind}  ', style='bold cyan')
        chat_status.append(selected_id[:16], style='cyan')
        chat_status.append(f'   {status}', style='bold yellow' if status == 'ACTIVE' else 'dim')
        chat_status.append(
            f'\nHistory page {page}/{page_count} · {len(self.session.messages)} messages',
            style='dim',
        )
        if self.session.unseen_messages:
            chat_status.append(
                f' · {self.session.unseen_messages} new',
                style='bold green',
            )
        if self.session.error:
            chat_status.append(f'\nDisconnected: {self.session.error} · retrying', style='red')
        elif self.session.warning:
            chat_status.append(f'\n{self.session.warning}', style='yellow')
        elif self.session.notice:
            chat_status.append(f'\n{self.session.notice}', style='green')
        elif self.session.last_refresh:
            chat_status.append(
                f'\nLive · refreshed {self.session.last_refresh.strftime("%H:%M:%S UTC")}',
                style='green',
            )
        self.query_one('#chat-status', Static).update(chat_status)

        pending = len(self.session.pending_interactions)
        selected_pending = self.session.selected_pending_count
        interaction_text = Text()
        if pending:
            interaction_text.append(f'⚠ {pending} PENDING INTERACTION(S)', style='bold yellow')
            interaction_text.append(
                f' · {selected_pending} in selected conversation · Ctrl+I review safely',
                style='yellow',
            )
        else:
            interaction_text.append('✓ No pending operator interactions', style='dim green')
        self.query_one('#interaction-status', Static).update(interaction_text)

        composer = self.query_one('#composer', Input)
        composer.disabled = not self.session.can_guide
        composer.placeholder = (
            'Guide the active root iteration, then press Enter'
            if self.session.can_guide
            else 'Read-only: select the active root iteration to send guidance'
        )

    async def _render_navigation(self, force):
        conversations = self.session.ordered_conversations
        fingerprint = tuple(
            (
                hunt_conversation_id(row),
                row.get('status'),
                row.get('parent_id'),
                row.get('title'),
                row.get('topic'),
            )
            for row in conversations
        )
        navigator = self.query_one('#conversation-list', ListView)
        if force or fingerprint != self._navigator_fingerprint:
            await navigator.clear()
            if conversations:
                await navigator.extend(
                    ConversationListItem(row, conversations)
                    for row in conversations
                )
            self._navigator_fingerprint = fingerprint
        identifiers = [hunt_conversation_id(row) for row in conversations]
        if self.session.selected_id in identifiers:
            navigator.index = identifiers.index(self.session.selected_id)

    async def _render_transcript(self, force):
        visible = self.session.visible_messages
        fingerprint = _message_fingerprint(
            self.session.selected_id,
            self.session.history_page,
            visible,
            self.session.expanded_tools,
        )
        if not force and fingerprint == self._transcript_fingerprint:
            return
        transcript = self.query_one('#transcript', VerticalScroll)
        await transcript.remove_children()
        widgets = []
        if not visible:
            widgets.append(Static(Panel('No messages yet.', border_style='dim')))
        for index, message in enumerate(visible):
            if message.get('role') == 'tool call':
                key = hunt_tool_key(message, index)
                widgets.append(ToolActivity(
                    message,
                    index,
                    expanded=key in self.session.expanded_tools,
                ))
            else:
                widgets.append(Static(build_live_message(message)))
        await transcript.mount(*widgets)
        self._transcript_fingerprint = fingerprint
        if self.session.history_page == 0:
            transcript.scroll_end(animate=False)
        else:
            transcript.scroll_home(animate=False)


def run_live_hunt_chat(
    sdk,
    hunt_id,
    *,
    requested_id=None,
    exact_requested_id=False,
    refresh_interval=DEFAULT_CHAT_REFRESH_SECONDS,
    review_interactions=None,
    app_factory=HuntChatApp,
):
    """Run chat until cancelled, temporarily suspending for shared HITL prompts."""
    session = HuntChatSession(
        sdk,
        hunt_id,
        requested_id=requested_id,
        exact_requested_id=exact_requested_id,
        refresh_interval=refresh_interval,
    )
    session.refresh(raise_errors=True)
    while True:
        try:
            outcome = app_factory(session).run()
        except KeyboardInterrupt:
            break
        if outcome != 'review-interactions':
            break
        if review_interactions is None:
            session.notice = 'Use the Hunt interactions command to answer requests.'
            continue
        try:
            review_interactions(list(session.pending_interactions))
        except KeyboardInterrupt:
            break
        session.refresh()
    return session


def group_hunt_tool_messages(messages):
    """Fold tool responses into calls even for partially normalized transcripts."""
    rows = [dict(row) for row in messages or [] if isinstance(row, dict)]
    responses = {}
    for row in rows:
        if row.get('role') not in ('tool response', 'tool_response'):
            continue
        identifier = _tool_use_id(row)
        if identifier:
            responses[identifier] = row

    grouped = []
    for row in rows:
        role = row.get('role')
        if role in ('tool response', 'tool_response'):
            if not _tool_use_id(row):
                grouped.append({
                    **row,
                    'role': 'tool call',
                    'tool': {
                        'name': 'tool response',
                        'input': None,
                        'response': row.get('content'),
                    },
                })
            continue
        if role in ('tool call', 'tool_call'):
            row['role'] = 'tool call'
            tool = dict(row.get('tool') or {}) if isinstance(row.get('tool'), dict) else {}
            identifier = _tool_use_id(row)
            if tool.get('response') is None and identifier in responses:
                response = responses[identifier]
                tool['response'] = response.get('content')
                for field in (
                    'attachments', 'attachment', 'screenshots', 'screenshot',
                ):
                    if response.get(field) is not None:
                        tool[field] = response[field]
            row['tool'] = tool
        grouped.append(row)
    return grouped


def build_live_message(message):
    role = str(message.get('role') or 'unknown')
    label, style, symbol = ROLE_PRESENTATION.get(
        role,
        (role.upper(), 'white', '•'),
    )
    content = _terminal_safe_text(message.get('content'), MAX_MESSAGE_CHARACTERS) or '—'
    body = [RichMarkdown(content)]
    attachments = safe_hunt_attachment_metadata(message)
    if attachments:
        attachment_text = Text('\n')
        attachment_text.append('\n'.join(attachments), style='dim cyan')
        body.append(attachment_text)
    timestamp = _terminal_safe_text(message.get('timestamp'), 80)
    return Panel(
        Group(*body),
        title=Text(f'{symbol} {label}', style=f'bold {style}'),
        subtitle=Text(timestamp, style='dim'),
        border_style=style,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def build_live_tool_activity(message, expanded=False):
    tool = message.get('tool') if isinstance(message.get('tool'), dict) else {}
    name = _terminal_safe_text(tool.get('name') or 'tool', 80)
    response = tool.get('response')
    completed = response is not None
    style = 'green' if completed else 'yellow'
    state = 'COMPLETED' if completed else 'RUNNING'
    summary = Text()
    summary.append('▾ ' if expanded else '▸ ', style='cyan')
    summary.append(name, style=f'bold {style}')
    summary.append(f'  {state}', style=style)
    summary.append('  Enter/Space details', style='dim')
    attachments = safe_hunt_attachment_metadata(tool)
    if attachments:
        summary.append(f'\n{" · ".join(attachments)}', style='dim cyan')
    if not expanded:
        return Panel(summary, border_style=style, box=box.SQUARE)

    input_text = format_live_tool_details(tool.get('input'))
    response_text = (
        format_live_tool_details(response)
        if completed
        else 'Waiting for the grouped tool response.'
    )
    details = Group(
        summary,
        Text('\nINPUT', style='bold bright_black'),
        Syntax(input_text, 'json', word_wrap=True, background_color='default'),
        Text('\nRESPONSE', style='bold bright_black'),
        Syntax(response_text, 'json', word_wrap=True, background_color='default'),
    )
    return Panel(details, border_style=style, box=box.SQUARE, padding=(0, 1))


def format_live_tool_details(value):
    """Bound, control-character sanitize, and redact common secret fields."""
    sanitized = _sanitize_tool_value(value)
    try:
        rendered = json.dumps(
            sanitized,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        rendered = json.dumps(_terminal_safe_text(sanitized, 1000))
    return _terminal_safe_text(rendered, MAX_TOOL_DETAIL_CHARACTERS)


def hunt_tool_key(message, index):
    identifier = _tool_use_id(message)
    if identifier:
        return identifier
    tool = message.get('tool') if isinstance(message.get('tool'), dict) else {}
    raw = '|'.join((
        str(message.get('timestamp') or ''),
        str(tool.get('name') or ''),
        str(index),
    ))
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:20]


def _tool_use_id(message):
    tool = message.get('tool') if isinstance(message.get('tool'), dict) else {}
    return str(
        tool.get('tool_use_id')
        or tool.get('toolUseId')
        or message.get('toolUseId')
        or message.get('tool_use_id')
        or ''
    )


def _sanitize_tool_value(value, depth=0):
    if depth >= MAX_TOOL_OBJECT_DEPTH:
        return '[nested data omitted]'
    if isinstance(value, dict):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_TOOL_COLLECTION_ITEMS:
                result['…'] = 'additional fields omitted'
                break
            safe_key = _terminal_safe_text(key, 128)
            result[safe_key] = (
                _REDACTED
                if _SENSITIVE_FIELD.search(safe_key)
                else _sanitize_tool_value(item, depth + 1)
            )
        return result
    if isinstance(value, (list, tuple)):
        items = [
            _sanitize_tool_value(item, depth + 1)
            for item in value[:MAX_TOOL_COLLECTION_ITEMS]
        ]
        if len(value) > MAX_TOOL_COLLECTION_ITEMS:
            items.append('[additional items omitted]')
        return items
    if isinstance(value, str):
        return _terminal_safe_text(value, 2000)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _terminal_safe_text(value, 500)


def _conversation_label(conversation, records):
    depth = hunt_conversation_depth(conversation, records)
    conversation_id = hunt_conversation_id(conversation)
    if depth:
        title = _terminal_safe_text(
            conversation.get('title') or conversation.get('topic'),
            54,
        ).removeprefix('Subagent: ')
        title = title or conversation_id[:12]
        title = f'{"  " * min(depth, 4)}↳ {title}'
    else:
        title = f'Iteration {conversation_id[:12]}'
    status = _terminal_safe_text(conversation.get('status') or 'unknown', 32).upper()
    label = Text(title, style='bold' if conversation.get('status') == 'active' else None)
    label.append(f'\n{status} · {conversation_id[:12]}', style='yellow' if status == 'ACTIVE' else 'dim')
    return label


def _message_fingerprint(selected_id, page, messages, expanded_tools):
    safe_rows = []
    for index, message in enumerate(messages):
        tool = message.get('tool') if isinstance(message.get('tool'), dict) else {}
        safe_rows.append((
            message.get('role'),
            _terminal_safe_text(message.get('timestamp'), 80),
            _terminal_safe_text(message.get('content'), MAX_MESSAGE_CHARACTERS),
            hunt_tool_key(message, index) if message.get('role') == 'tool call' else '',
            format_live_tool_details(tool) if tool else '',
            safe_hunt_attachment_metadata(message),
        ))
    raw = repr((selected_id, page, safe_rows, sorted(expanded_tools)))
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()


def _terminal_safe_text(value, limit):
    if value is None:
        return ''
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            value = str(value)
    value = _ANSI_ESCAPE.sub('', value).replace('\r\n', '\n').replace('\r', '\n')
    safe = ''.join(
        character
        if character in ('\n', '\t') or character.isprintable()
        else ' '
        for character in value
    )
    if len(safe) <= limit:
        return safe
    return safe[:max(0, limit - 1)] + '…'
