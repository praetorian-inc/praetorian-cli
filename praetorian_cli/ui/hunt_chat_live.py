import asyncio
import copy
import hashlib
import json
import math
import re
from contextlib import nullcontext
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

from praetorian_cli.ui.async_http import (
    install_shared_aiohttp_session,
    run_in_worker,
)
from praetorian_cli.ui.hunt_chat import (
    ROLE_PRESENTATION,
    hunt_conversation_depth,
    hunt_conversation_id,
    hunt_conversation_is_root,
    ordered_hunt_conversations,
    safe_hunt_attachment_metadata,
    select_hunt_conversation,
)
from praetorian_cli.ui.terminal import supports_fullscreen
from praetorian_cli.ui.textual_refresh import (
    REFRESH_SPINNER_FRAMES,
    RefreshModal,
    RefreshResult,
    start_background_task,
)


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
    return supports_fullscreen(input_stream, output_stream)


class HuntChatSession:
    """API-backed state for live chat, independent from the terminal widgets."""

    def __init__(
        self,
        sdk,
        hunt_id,
        *,
        requested_id=None,
        exact_requested_id=False,
        page_size=DEFAULT_HISTORY_PAGE_SIZE,
        request_pages=None,
        authorize_hunt=None,
    ):
        self.sdk = sdk
        self.hunt_id = str(hunt_id or '').strip()
        self.requested_id = requested_id
        self.exact_requested_id = bool(exact_requested_id)
        self.page_size = max(1, min(int(page_size), 100))
        self.request_pages = (
            max(1, int(request_pages)) if request_pages is not None else None
        )
        self.authorize_hunt = authorize_hunt
        self.conversations = []
        self.selected = None
        self.transcript = {'messages': []}
        self.transcript_cache = {}
        self._selection_version = 0
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
        """Refresh atomically without overwriting a newer user selection."""
        selection_version = self._selection_version
        try:
            if self.authorize_hunt is not None:
                self.authorize_hunt(self.hunt_id)
            conversations, _ = self.sdk.hunts.list_conversations(
                self.hunt_id,
                **self._page_kwargs,
            )
            requested = (
                self.requested_id
                if self.requested_id is not None
                else (self.selected_id or None)
            )
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
                **self._page_kwargs,
            )
        except Exception:
            pending = self.pending_interactions
            warning = 'Pending interactions are temporarily unavailable; retrying.'

        old_count = len(self.messages)
        same_selection = selected_id == self.selected_id
        self.conversations = [
            row for row in conversations or [] if isinstance(row, dict)
        ]
        if selection_version == self._selection_version:
            self.selected = selected
            self.requested_id = None
            self.transcript = self._cached_transcript(
                selected_id,
                transcript,
            )
            if not same_selection:
                self.history_page = 0
                self.unseen_messages = 0
            elif self.history_page:
                self.unseen_messages += max(0, len(self.messages) - old_count)
            else:
                self.unseen_messages = 0
            self.history_page = min(
                self.history_page,
                self.page_count - 1,
            )
        self.pending_interactions = [
            row for row in pending or []
            if isinstance(row, dict) and row.get('status') == 'pending'
        ]
        self.error = ''
        self.warning = warning
        self.consecutive_failures = 0
        self.last_refresh = datetime.now(timezone.utc)
        return True

    def select_conversation(self, conversation_id):
        """Select an authorized conversation, reusing visited transcripts."""
        try:
            selected = select_hunt_conversation(
                self.conversations,
                requested_id=conversation_id,
            )
            selected_id = hunt_conversation_id(selected)
            transcript = self.transcript_cache.get(selected_id)
            if transcript is None:
                transcript = self.sdk.conversations.get(selected_id)
        except Exception as exc:
            self._record_failure(exc)
            return False

        self._selection_version += 1
        self.selected = selected
        self.transcript = self._cached_transcript(selected_id, transcript)
        self.history_page = 0
        self.unseen_messages = 0
        self.error = ''
        self.notice = ''
        self.consecutive_failures = 0
        return True

    def cache_transcript(self, conversation_id, transcript):
        if isinstance(transcript, dict):
            self.transcript_cache[conversation_id] = copy.deepcopy(transcript)

    def _cached_transcript(self, conversation_id, transcript):
        normalized = (
            copy.deepcopy(transcript)
            if isinstance(transcript, dict)
            else {'messages': []}
        )
        self.transcript_cache[conversation_id] = copy.deepcopy(normalized)
        return normalized

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
            if self.authorize_hunt is not None:
                self.authorize_hunt(self.hunt_id)
            conversations, _ = self.sdk.hunts.list_conversations(
                self.hunt_id,
                **self._page_kwargs,
            )
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

    @property
    def _page_kwargs(self):
        return (
            {'pages': self.request_pages}
            if self.request_pages is not None
            else {}
        )

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
        def __init__(self, activity, expanded):
            self.activity = activity
            self.key = activity.tool_key
            self.expanded = expanded
            super().__init__()

    def __init__(self, message, index, renderable, expanded=False):
        self.message_record = message
        self.message_index = index
        self.tool_key = hunt_tool_key(message, index)
        self.expanded = expanded
        self._toggle_loading = False
        super().__init__(renderable)

    def on_key(self, event):
        if event.key not in ('enter', 'space') or self._toggle_loading:
            return
        self._toggle_loading = True
        self.post_message(self.Toggled(self, not self.expanded))
        event.stop()

    def apply_expansion(self, expanded, renderable):
        self.expanded = expanded
        self._toggle_loading = False
        self.update(renderable)
        self.refresh(layout=True)

    def cancel_expansion(self):
        self._toggle_loading = False


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
    #conversation-list {
        width: 100%; height: 1fr; background: #0f172a;
        overflow-x: hidden; overflow-y: auto;
    }
    #conversation-list > ListItem {
        width: 100%; max-width: 100%; padding: 0 1; height: auto;
    }
    #conversation-list > ListItem.--highlight { background: #23345d; }
    #chat-pane { width: 1fr; padding: 0 1; }
    #chat-status { height: 4; border-bottom: solid #a855f7; padding: 0 1; }
    #transcript {
        width: 1fr; height: 1fr; padding: 1 0;
        overflow-x: hidden; overflow-y: auto;
        scrollbar-size-vertical: 1;
    }
    #transcript > Static, #transcript > ToolActivity {
        width: 100%; max-width: 100%; height: auto; margin: 0 0 1 0;
    }
    ToolActivity:focus { border: tall #67e8f9; }
    #interaction-status { height: 2; color: #facc15; padding: 0 1; }
    #composer { dock: bottom; height: 3; border: tall #a855f7; }
    #composer:disabled { border: tall #475569; color: #94a3b8; }
    Footer { background: #111827; }
    """
    BINDINGS = [
        Binding('up', 'previous_conversation', 'previous conversation', priority=True),
        Binding('down', 'next_conversation', 'next conversation', priority=True),
        Binding('ctrl+p', 'previous_conversation', '', show=False, priority=True),
        Binding('ctrl+n', 'next_conversation', '', show=False, priority=True),
        Binding('pageup', 'older_history', 'older history', priority=True),
        Binding('pagedown', 'newer_history', 'newer history', priority=True),
        Binding('ctrl+r', 'force_refresh', 'refresh', priority=True),
        Binding('f8', 'review_interactions', 'interactions', priority=True),
        Binding('ctrl+c', 'cancel_chat', 'back', priority=True),
        Binding(
            'escape',
            'cancel_chat',
            'back',
            show=False,
            priority=True,
        ),
    ]

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.sub_title = (
            f'Hunt {_terminal_safe_text(session.hunt_id, 48)} · live operator view'
        )
        self._refresh_lock = asyncio.Lock()
        self._active_refresh_task = None
        self._refresh_modal = None
        self._loading = False
        self._loading_message = 'Loading…'
        self._spinner_index = 0
        self._tool_toggle_task = None
        self._background_tasks = set()
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
        self.set_interval(0.1, self._advance_loading_spinner)
        self.query_one('#composer', Input).focus()

    def on_unmount(self):
        self._cancel_active_refresh()
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()

    def _start_background_task(self, coroutine):
        return start_background_task(
            self._background_tasks,
            coroutine,
            on_error=self._background_task_failed,
        )

    def _background_task_failed(self, error):
        self.session._record_failure(error)
        if self.is_running:
            self.call_after_refresh(self._render_state)

    def _start_active_request(
        self,
        operation,
        *,
        force=False,
        replace=False,
        show_loading=False,
    ):
        task = self._active_refresh_task
        if task is not None and not task.done():
            if not replace:
                return task
            self._cancel_active_refresh()
        task = self._start_background_task(
            self._run_request(
                operation,
                force=force,
                show_loading=show_loading,
            )
        )
        self._active_refresh_task = task
        task.add_done_callback(self._active_refresh_finished)
        return task

    def _active_refresh_finished(self, task):
        if self._active_refresh_task is task:
            self._active_refresh_task = None

    def _cancel_active_refresh(self):
        task = self._active_refresh_task
        if task is not None and not task.done():
            task.cancel()
        self._active_refresh_task = None

    async def _run_request(self, operation, force=False, show_loading=False):
        if show_loading:
            self._set_loading()
        try:
            async with self._refresh_lock:
                await run_in_worker(operation)
        finally:
            if (
                self.is_running
                and self._active_refresh_task is asyncio.current_task()
            ):
                self._clear_loading()
                await self._render_state(force=force)
        return True

    @on(ListView.Highlighted, '#conversation-list')
    def _conversation_highlighted(self, event):
        item = event.item
        navigator = self.query_one('#conversation-list', ListView)
        if item is not navigator.highlighted_child:
            return
        if (
            isinstance(item, ConversationListItem)
            and item.conversation_id != self.session.selected_id
        ):
            self._start_active_request(
                lambda: self.session.select_conversation(
                    item.conversation_id
                ),
                force=True,
                replace=True,
                show_loading=True,
            )

    @on(Input.Submitted, '#composer')
    def _guidance_submitted(self, event):
        message = event.value
        if not message.strip():
            return
        if not self.session.can_guide:
            self.session.error = 'Guidance is available only for the active root iteration.'
            self._start_background_task(self._render_state())
            return
        composer = self.query_one('#composer', Input)
        composer.disabled = True
        self._cancel_active_refresh()
        task = self._start_background_task(
            self._submit_guidance(message, composer)
        )
        self._active_refresh_task = task
        task.add_done_callback(self._active_refresh_finished)

    async def _submit_guidance(self, message, composer):
        try:
            async with self._refresh_lock:
                await run_in_worker(self.session.send_guidance, message)
                await run_in_worker(self.session.refresh)
        except Exception:
            pass
        else:
            composer.value = ''
        finally:
            if (
                self.is_running
                and self._active_refresh_task is asyncio.current_task()
            ):
                await self._render_state(force=True)

    @on(ToolActivity.Toggled)
    def _tool_toggled(self, event):
        task = self._tool_toggle_task
        if task is not None and not task.done():
            event.activity.cancel_expansion()
            return
        self._set_loading('Loading details…')
        task = self._start_background_task(
            self._toggle_tool(event.activity, event.expanded)
        )
        self._tool_toggle_task = task
        task.add_done_callback(self._tool_toggle_finished)

    def _tool_toggle_finished(self, task):
        if self._tool_toggle_task is task:
            self._tool_toggle_task = None

    async def _toggle_tool(self, activity, expanded):
        try:
            renderable = await run_in_worker(
                build_live_tool_activity,
                activity.message_record,
                expanded,
            )
            if expanded:
                self.session.expanded_tools.add(activity.tool_key)
            else:
                self.session.expanded_tools.discard(activity.tool_key)
            activity.apply_expansion(expanded, renderable)
        except Exception as exc:
            activity.cancel_expansion()
            self.session._record_failure(exc)
        finally:
            if self.is_running:
                self._clear_loading()
                self._render_interaction_status()

    def action_previous_conversation(self):
        self._move_conversation(-1)

    def action_next_conversation(self):
        self._move_conversation(1)

    def _move_conversation(self, delta):
        self._start_active_request(
            lambda: self.session.move_selection(delta),
            force=True,
            replace=True,
            show_loading=True,
        )

    def _set_loading(self, message='Loading…'):
        self._loading = True
        self._loading_message = message
        self._spinner_index = 0
        self._render_interaction_status()

    def _clear_loading(self):
        self._loading = False
        self._loading_message = 'Loading…'

    def _advance_loading_spinner(self):
        if not self._loading:
            return
        self._spinner_index = (
            self._spinner_index + 1
        ) % len(REFRESH_SPINNER_FRAMES)
        self._render_interaction_status()

    async def action_older_history(self):
        if self.session.older_history():
            await self._render_state(force=True)

    async def action_newer_history(self):
        if self.session.newer_history():
            await self._render_state(force=True)

    def action_force_refresh(self):
        if self._refresh_modal is not None:
            return
        self._cancel_active_refresh()
        modal = RefreshModal('CHAT', self._manual_refresh)
        self._refresh_modal = modal
        self.push_screen(
            modal,
            lambda result: self._manual_refresh_finished(modal, result),
        )

    async def _manual_refresh(self):
        async with self._refresh_lock:
            return await run_in_worker(self.session.refresh)

    def _manual_refresh_finished(self, modal, result: RefreshResult):
        if self._refresh_modal is modal:
            self._refresh_modal = None
        if not isinstance(result, RefreshResult):
            return
        if result.error is not None:
            self.session._record_failure(result.error)
        if self.is_running:
            self._start_background_task(self._render_state(force=True))

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

        self._render_interaction_status()

        composer = self.query_one('#composer', Input)
        composer.disabled = not self.session.can_guide
        composer.placeholder = (
            'Guide the active root iteration, then press Enter'
            if self.session.can_guide
            else 'Read-only: select the active root iteration to send guidance'
        )

    def _render_interaction_status(self):
        interaction_text = Text()
        if self._loading:
            frame = REFRESH_SPINNER_FRAMES[self._spinner_index]
            interaction_text.append(
                f'{frame} {self._loading_message}',
                style='cyan',
            )
        else:
            pending = len(self.session.pending_interactions)
            selected_pending = self.session.selected_pending_count
            if pending:
                interaction_text.append(
                    f'⚠ {pending} PENDING INTERACTION(S)',
                    style='bold yellow',
                )
                interaction_text.append(
                    f' · {selected_pending} in selected conversation'
                    ' · F8 review safely',
                    style='yellow',
                )
            else:
                interaction_text.append(
                    '✓ No pending operator interactions',
                    style='dim green',
                )
        self.query_one('#interaction-status', Static).update(interaction_text)

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
        if fingerprint != self._navigator_fingerprint:
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
        prepared = await run_in_worker(
            _prepare_live_transcript,
            visible,
            self.session.expanded_tools,
        )
        widgets = []
        for kind, value, index, expanded, renderable in prepared:
            if kind == 'tool':
                widgets.append(ToolActivity(
                    value,
                    index,
                    renderable,
                    expanded=expanded,
                ))
            else:
                widgets.append(Static(renderable))
        transcript = self.query_one('#transcript', VerticalScroll)
        await transcript.remove_children()
        await transcript.mount(*widgets)
        transcript.scroll_end(animate=False)
        self._transcript_fingerprint = fingerprint


def run_live_hunt_chat(
    sdk,
    hunt_id,
    *,
    requested_id=None,
    exact_requested_id=False,
    request_pages=None,
    authorize_hunt=None,
    review_interactions=None,
    console=None,
    app_factory=HuntChatApp,
):
    """Run chat until cancelled, temporarily suspending for shared HITL prompts."""
    session = HuntChatSession(
        sdk,
        hunt_id,
        requested_id=requested_id,
        exact_requested_id=exact_requested_id,
        request_pages=request_pages,
        authorize_hunt=authorize_hunt,
    )
    shared_http = install_shared_aiohttp_session(sdk)
    try:
        return _run_live_hunt_chat_session(
            session,
            console=console,
            review_interactions=review_interactions,
            app_factory=app_factory,
        )
    finally:
        shared_http.close()


def _run_live_hunt_chat_session(
    session,
    *,
    console,
    review_interactions,
    app_factory,
):
    feedback = (
        console.status('Loading chats…', spinner='dots')
        if console is not None
        else nullcontext()
    )
    with feedback:
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


def _prepare_live_transcript(messages, expanded_tools):
    if not messages:
        return [(
            'message',
            None,
            0,
            False,
            Panel('No messages yet.', border_style='dim'),
        )]
    prepared = []
    for index, message in enumerate(messages):
        if message.get('role') == 'tool call':
            key = hunt_tool_key(message, index)
            expanded = key in expanded_tools
            prepared.append((
                'tool',
                message,
                index,
                expanded,
                build_live_tool_activity(message, expanded),
            ))
        else:
            prepared.append((
                'message',
                message,
                index,
                False,
                build_live_message(message),
            ))
    return prepared


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
