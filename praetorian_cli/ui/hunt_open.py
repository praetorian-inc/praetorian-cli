import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Input, Static, Tab, Tabs

from praetorian_cli.ui.async_http import (
    install_shared_aiohttp_session,
    run_in_worker,
)
from praetorian_cli.ui.conversation.endpoint_status import (
    format_endpoint_execution_status,
)
from praetorian_cli.ui.hunt_chat import (
    build_hunt_chat,
    build_hunt_interactions,
)
from praetorian_cli.ui.hunt_chat_live import HuntChatSession, run_live_hunt_chat
from praetorian_cli.ui.hunt_data import build_hunt_findings, build_hunt_log
from praetorian_cli.ui.hunt_memory import (
    MEMORY_REFRESH_MAX_PAGES,
    HuntMemoryBrowser,
    browse_hunt_memory,
    build_hunt_memory_browser,
)
from praetorian_cli.ui.hunt_overview import build_hunt_overview
from praetorian_cli.ui.hunt_workflows import (
    WorkflowBrowser,
    build_hunt_workflow_browser,
    build_hunt_workflows,
)
from praetorian_cli.ui.terminal import supports_fullscreen
from praetorian_cli.ui.textual_refresh import (
    RefreshModal,
    RefreshResult,
    start_background_task,
)


HUNT_OPEN_VIEWS = (
    'overview',
    'vulnerabilities',
    'workflow',
    'log',
    'memory',
    'chat',
    'approvals',
)
HUNT_OPEN_LABELS = {
    'overview': '1 Overview',
    'vulnerabilities': '2 Vulnerabilities',
    'workflow': '3 Workflow',
    'log': '4 Log',
    'memory': '5 Memory',
    'chat': '6 Chat',
    'approvals': '7 Approvals',
}
HUNT_OPEN_REFRESH_MAX_PAGES = 10
MAX_HUNT_OPEN_FINDINGS = 250
MAX_HUNT_OPEN_WORKFLOWS = 100
MAX_HUNT_OPEN_LOG_CHARACTERS = 100_000
HUNT_OPEN_SPINNER_FRAMES = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')
HUNT_OPEN_SPINNER_INTERVAL_SECONDS = 0.1


def supports_fullscreen_hunt_open(input_stream=None, output_stream=None):
    """Return whether the unified Hunt app can safely own the terminal."""
    return supports_fullscreen(input_stream, output_stream)


class HuntOpenSession:
    """Bounded, failure-tolerant state shared across unified Hunt app runs."""

    def __init__(
        self,
        sdk,
        hunt_id,
        *,
        initial_hunt=None,
        authorize_hunt=None,
    ):
        self.sdk = sdk
        self.hunt_id = str(hunt_id or '').strip().removeprefix('#hunt#')
        self.authorize_hunt = authorize_hunt
        self.hunt = dict(initial_hunt) if isinstance(initial_hunt, dict) else None
        self.active_view = 'overview'
        self.loaded_views = set()
        self.view_errors = {}
        self._render_cache = {}
        self.notice = ''
        self.last_refresh = None

        self.overview = None
        self.endpoint_status = ''
        self.findings = []
        self.finding_cursor = 0
        self.workflow_browser = None
        self.log_content = ''
        self.log_truncated = False
        self.memory_browser = None
        self.pending_interactions = []
        self.interaction_warning = ''
        self.requested_chat_id = None
        self.chat_session = HuntChatSession(
            sdk,
            self.hunt_id,
            request_pages=HUNT_OPEN_REFRESH_MAX_PAGES,
            authorize_hunt=authorize_hunt,
        )

    @property
    def status(self):
        return str((self.hunt or {}).get('status') or 'unknown').lower()

    @property
    def current_finding(self):
        if 0 <= self.finding_cursor < len(self.findings):
            return self.findings[self.finding_cursor]
        return None

    def revalidate(self):
        """Reload the Hunt through the caller's ownership boundary."""
        if self.authorize_hunt is not None:
            hunt = self.authorize_hunt(self.hunt_id)
        else:
            hunt = self.sdk.hunts.get(self.hunt_id)
        if not isinstance(hunt, dict):
            raise ValueError(f'Hunt {self.hunt_id} not found')
        self.hunt = dict(hunt)
        return self.hunt

    def refresh(self, view=None, *, raise_errors=False):
        """Refresh one view's data and cached Rich snapshot."""
        view = view or self.active_view
        if view not in HUNT_OPEN_VIEWS:
            raise ValueError(f'unknown Hunt view: {view}')
        try:
            self.revalidate()
        except Exception as exc:
            self.view_errors[view] = _safe(str(exc) or exc.__class__.__name__, 400)
            if raise_errors:
                raise
            return False

        loader = getattr(self, f'_refresh_{view}')
        try:
            loader()
        except Exception as exc:
            self.view_errors[view] = _safe(str(exc) or exc.__class__.__name__, 400)
            if raise_errors:
                raise
            return False

        self.view_errors.pop(view, None)
        self.loaded_views.add(view)
        self.rebuild_view(view)
        self.last_refresh = datetime.now(timezone.utc)
        return True

    def select_view(self, view):
        if view not in HUNT_OPEN_VIEWS:
            return False
        self.active_view = view
        return True

    def move_context_cursor(self, delta):
        """Move the active view's supported cursor without changing tabs."""
        moved = False
        if self.active_view == 'memory' and self.memory_browser is not None:
            moved = self.memory_browser.move(delta)
        elif self.active_view == 'workflow' and self.workflow_browser is not None:
            moved = self.workflow_browser.move(delta)
        elif self.active_view == 'chat':
            moved = self.chat_session.move_selection(delta)
        elif self.active_view == 'vulnerabilities' and self.findings:
            previous = self.finding_cursor
            self.finding_cursor = min(
                max(previous + delta, 0),
                len(self.findings) - 1,
            )
            moved = previous != self.finding_cursor
        if moved:
            self.invalidate_view()
        return moved

    def perform_lifecycle(self, action):
        """Revalidate authorization immediately before an SDK lifecycle call."""
        allowed = {
            'pause': {'active'},
            'resume': {'paused'},
            'stop': {'active', 'paused'},
        }
        self.revalidate()
        if self.status not in allowed[action]:
            raise ValueError(
                f'Hunt {self.hunt_id} cannot {action} while {self.status}'
            )
        result = getattr(self.sdk.hunts, action)(self.hunt_id)
        self.notice = f'Hunt {self.hunt_id} {action} request accepted.'
        self.revalidate()
        return result

    def render(self, view=None):
        view = view or self.active_view
        renderable = self._render_cache.get(view)
        if renderable is None:
            self.rebuild_view(view)
            renderable = self._render_cache[view]
        messages = []
        if self.view_errors.get(view):
            messages.append(Panel(
                Text(
                    f'{HUNT_OPEN_LABELS[view].split(" ", 1)[1]} refresh failed: '
                    f'{self.view_errors[view]}\nShowing the last successful snapshot.',
                    style='yellow',
                ),
                border_style='yellow',
            ))
        if self.notice:
            messages.append(Text(self.notice, style='green'))
        if messages:
            return Group(*messages, Text(''), renderable)
        return renderable

    def invalidate_view(self, view=None):
        self._render_cache.pop(view or self.active_view, None)

    def rebuild_view(self, view=None):
        view = view or self.active_view
        self._render_cache[view] = self._build_view(view)
        return self._render_cache[view]

    def _build_view(self, view):
        return {
            'overview': lambda: build_hunt_open_overview(self),
            'vulnerabilities': lambda: _build_vulnerabilities(self),
            'workflow': lambda: _build_workflow(self),
            'log': lambda: build_hunt_log(self.log_content),
            'memory': lambda: _build_memory(self),
            'chat': lambda: _build_chat(self),
            'approvals': lambda: build_hunt_interactions(
                self.pending_interactions,
            ),
        }[view]()

    def _refresh_overview(self):
        cost_status = None
        root_agents = None
        findings = None
        overview_errors = []
        try:
            cost_status = self.sdk.hunts.get_cost(self.hunt_id)
        except Exception as exc:
            overview_errors.append(f'cost: {_safe(exc, 120)}')
        try:
            root_agents, _ = self.sdk.hunts.list_root_conversations(
                self.hunt_id,
                pages=HUNT_OPEN_REFRESH_MAX_PAGES,
            )
        except Exception as exc:
            overview_errors.append(f'agents: {_safe(exc, 120)}')
        try:
            findings, _ = self.sdk.hunts.list_findings(
                self.hunt_id,
                pages=HUNT_OPEN_REFRESH_MAX_PAGES,
            )
        except Exception as exc:
            overview_errors.append(f'vulnerabilities: {_safe(exc, 120)}')
        self.overview = build_hunt_overview(
            self.sdk,
            self.hunt,
            cost_status=cost_status,
            root_agents=root_agents,
            findings=findings,
        )
        try:
            endpoint_status = self.sdk.hunts.endpoint_execution_status(self.hunt)
            self.endpoint_status = format_endpoint_execution_status(endpoint_status)
        except Exception as exc:
            self.endpoint_status = ''
            overview_errors.append(f'endpoint: {_safe(exc, 120)}')
        if overview_errors:
            self.notice = 'Some overview metrics are unavailable · ' + ' · '.join(
                overview_errors
            )
        elif self.notice.startswith('Some overview metrics are unavailable'):
            self.notice = ''

    def _refresh_vulnerabilities(self):
        selected_key = _finding_key(self.current_finding)
        findings, next_offset = self.sdk.hunts.list_findings(
            self.hunt_id,
            pages=HUNT_OPEN_REFRESH_MAX_PAGES,
        )
        self.findings = [
            row for row in findings or [] if isinstance(row, dict)
        ][:MAX_HUNT_OPEN_FINDINGS]
        self.finding_cursor = _restored_index(
            self.findings,
            selected_key,
            _finding_key,
            self.finding_cursor,
        )
        if next_offset or len(findings or []) > len(self.findings):
            self.notice = (
                f'Vulnerability view is bounded to {len(self.findings)} loaded records.'
            )
        elif self.notice.startswith('Vulnerability view is bounded'):
            self.notice = ''

    def _refresh_workflow(self):
        previous = self.workflow_browser
        selected_id = _workflow_key(previous.current) if previous else ''
        selected_step_index = (
            previous.current_step_index if previous else None
        )
        expanded_ids = {
            _workflow_key(previous.runs[index])
            for index in previous.expanded
            if 0 <= index < len(previous.runs)
        } if previous else set()
        runs, next_offset = self.sdk.hunts.list_workflow_runs(
            self.hunt_id,
            pages=HUNT_OPEN_REFRESH_MAX_PAGES,
        )
        records = [row for row in runs or [] if isinstance(row, dict)]
        browser = WorkflowBrowser(records[:MAX_HUNT_OPEN_WORKFLOWS])
        browser.cursor = _restored_index(
            browser.runs,
            selected_id,
            _workflow_key,
            previous.cursor if previous else 0,
        )
        restored_expanded = {
            index for index, row in enumerate(browser.runs)
            if _workflow_key(row) in expanded_ids
        }
        if previous is not None:
            # Preserve an explicitly empty expansion set; WorkflowBrowser's
            # default expands the first run only for the initial load.
            browser.expanded = restored_expanded
            if selected_step_index in browser.step_indices:
                browser.step_cursors[browser.cursor] = selected_step_index
            browser.step_mode = (
                previous.step_mode
                and bool(browser.step_indices)
            )
        self.workflow_browser = browser
        if next_offset or len(records) > len(browser.runs):
            self.notice = (
                f'Workflow view is bounded to {len(browser.runs)} loaded runs.'
            )
        elif self.notice.startswith('Workflow view is bounded'):
            self.notice = ''

    def _refresh_log(self):
        content = str(self.sdk.hunts.get_log(self.hunt_id) or '')
        self.log_truncated = len(content) > MAX_HUNT_OPEN_LOG_CHARACTERS
        self.log_content = content[-MAX_HUNT_OPEN_LOG_CHARACTERS:]
        if self.log_truncated:
            self.notice = (
                f'Log view shows the latest {MAX_HUNT_OPEN_LOG_CHARACTERS:,} characters.'
            )
        elif self.notice.startswith('Log view shows the latest'):
            self.notice = ''

    def _refresh_memory(self):
        if self.memory_browser is None:
            items, next_offset = self.sdk.hunts.list_memory(
                self.hunt_id,
                pages=MEMORY_REFRESH_MAX_PAGES,
            )
            self.memory_browser = HuntMemoryBrowser(
                self.sdk.hunts,
                self.hunt_id,
                items,
                next_offset=next_offset,
            )
            self.memory_browser.load_current()
            return
        if (
            self.memory_browser.mode == 'browse'
            and not self.memory_browser.refresh()
            and self.memory_browser.status
        ):
            raise RuntimeError(self.memory_browser.status)

    def _refresh_chat(self):
        if self.chat_session.refresh():
            self.pending_interactions = list(
                self.chat_session.pending_interactions
            )
            self.interaction_warning = self.chat_session.warning

    def _refresh_approvals(self):
        self._refresh_pending_interactions()

    def _refresh_pending_interactions(self):
        rows = self.sdk.hunts.list_interactions(
            self.hunt_id,
            status='pending',
            pages=HUNT_OPEN_REFRESH_MAX_PAGES,
        )
        self.pending_interactions = [
            row for row in rows or []
            if isinstance(row, dict) and row.get('status') == 'pending'
        ]
        self.chat_session.pending_interactions = list(self.pending_interactions)
        self.interaction_warning = ''
        self.invalidate_view('approvals')
        self.invalidate_view('chat')


def build_hunt_open_overview(session):
    overview = session.overview or {
        'remaining': '—',
        'projected_cost': '—',
        'root_agent': '—',
        'root_agent_count': '—',
        'iterations': 0,
        'highest_severity': '—',
        'scope_summary': '—',
        'agent_summary': '—',
    }
    hunt = session.hunt or {}
    table = Table(
        title=Text(f'Hunt {session.hunt_id} overview', style='bold cyan'),
        box=box.ROUNDED,
        border_style='cyan',
        expand=True,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column('FIELD', style='bold bright_black', width=20)
    table.add_column('VALUE', ratio=1)
    fields = (
        ('Status', str(hunt.get('status') or 'unknown').upper()),
        ('Remaining', overview['remaining']),
        ('Projected cost', overview['projected_cost']),
        ('Root agent', overview['root_agent']),
        ('Root agents', overview['root_agent_count']),
        ('Iterations', overview['iterations']),
        ('Findings', hunt.get('findingsCount', hunt.get('findings_count', 0))),
        ('Highest severity', overview['highest_severity']),
        ('Scope', overview['scope_summary']),
        ('Agent activity', overview['agent_summary']),
        ('Objective', hunt.get('prompt') or '—'),
    )
    for label, value in fields:
        table.add_row(Text(label), Text(_safe(value, 1000) or '—'))
    renderables = [table]
    if session.endpoint_status:
        renderables.extend([
            Text(''),
            Panel(
                Text(session.endpoint_status),
                title='Endpoint execution',
                border_style='magenta',
            ),
        ])
    return Group(*renderables)


def build_hunt_open_header(session):
    hunt = session.hunt or {}
    text = Text()
    text.append('⚔ HANNIBAL HUNT  ', style='bold cyan')
    text.append(session.hunt_id, style='cyan')
    text.append('   ')
    status = str(hunt.get('status') or 'unknown').upper()
    text.append(status, style='bold yellow' if status in ('ACTIVE', 'PAUSED') else 'dim')
    findings = hunt.get('findingsCount', hunt.get('findings_count', 0))
    text.append(f'   {findings or 0} findings', style='white')
    if session.last_refresh:
        text.append(
            f'   refreshed {session.last_refresh.strftime("%H:%M:%S UTC")}',
            style='dim green',
        )
    return text


def _build_vulnerabilities(session):
    renderable = build_hunt_findings(session.findings)
    if not session.findings:
        return renderable
    finding = session.current_finding or {}
    risk = (
        finding.get('risk')
        if isinstance(finding.get('risk'), dict)
        else finding
    )
    selected = risk.get('title') or risk.get('name') or _finding_key(finding)
    return Group(
        Text(
            f'↑/↓ select · {session.finding_cursor + 1}/{len(session.findings)} '
            f'· {_safe(selected, 120)}',
            style='dim',
        ),
        renderable,
    )


def _build_workflow(session):
    browser = session.workflow_browser
    if browser is None:
        return build_hunt_workflows([])
    position = browser.cursor + 1 if browser.runs else 0
    selected = browser.current or {}
    selected_label = (
        selected.get('title')
        or selected.get('definition')
        or _workflow_key(selected)
        or '—'
    )
    return Group(
        Text(
            f'↑/↓ select · Enter choose/open · Space collapse · '
            f'{position}/{len(browser.runs)} '
            f'· {_safe(selected_label, 120)}',
            style='dim',
        ),
        build_hunt_workflow_browser(browser),
    )


def _build_memory(session):
    if session.memory_browser is None:
        return Panel('No memory items loaded.', title='Hunt memory', border_style='dim')
    return Group(
        Text(
            '↑/↓ select item · Enter/m editor · n new memory item',
            style='dim',
        ),
        build_hunt_memory_browser(session.memory_browser, embedded=True),
    )


def _build_chat(session):
    chat = session.chat_session
    if chat.selected is None:
        detail = chat.error or 'This Hunt has no conversations yet.'
        return Panel(
            Text(detail, style='dim'),
            title='Hannibal Hunt Chat',
            border_style='dim',
        )
    return Group(
        Text('↑/↓ select conversation · Enter/c opens live chat', style='dim'),
        build_hunt_chat(
            chat.conversations,
            chat.selected,
            chat.transcript,
            pending_interactions=chat.pending_interactions,
        ),
    )


class HuntOpenApp(App):
    """Unified fullscreen operational interface for one Hunt."""

    TITLE = 'Hannibal Hunt'
    SUB_TITLE = 'unified operator view'
    CSS = """
    Screen { background: #090d18; color: #e8e8ee; }
    #hunt-header { height: 3; padding: 1 2; background: #111827; }
    Tabs { height: 3; }
    #view-scroll {
        width: 1fr; height: 1fr;
        overflow-x: hidden; overflow-y: auto;
        scrollbar-size-vertical: 1;
    }
    #view-content { width: 100%; max-width: 100%; height: auto; padding: 1 2; }
    #steering { height: 3; border: tall #a855f7; margin: 0 1; }
    #steering:disabled { border: tall #475569; color: #94a3b8; }
    #operator-status { height: 2; padding: 0 2; color: #facc15; }
    Footer { background: #111827; }
    """
    BINDINGS = [
        Binding(
            'left',
            'previous_view',
            'previous view',
            priority=True,
        ),
        Binding(
            'right',
            'next_view',
            'next view',
            priority=True,
        ),
        Binding('1', 'view_1', 'overview', show=False),
        Binding('2', 'view_2', 'vulnerabilities', show=False),
        Binding('3', 'view_3', 'workflow', show=False),
        Binding('4', 'view_4', 'log', show=False),
        Binding('5', 'view_5', 'memory', show=False),
        Binding('6', 'view_6', 'chat', show=False),
        Binding('7', 'view_7', 'approvals', show=False),
        Binding(
            'up',
            'context_up',
            'previous item',
            priority=True,
        ),
        Binding(
            'down',
            'context_down',
            'next item',
            priority=True,
        ),
        Binding('enter', 'activate_context', 'select', show=False),
        Binding('space', 'toggle_context', 'expand', show=False),
        Binding('r', 'force_refresh', 'refresh'),
        Binding('m', 'memory_editor', 'memory editor'),
        Binding('n', 'new_memory', 'new memory', show=False),
        Binding('c', 'live_chat', 'live chat'),
        Binding('i', 'review_approvals', 'review approvals'),
        Binding('p', 'pause_hunt', 'pause'),
        Binding('u', 'resume_hunt', 'resume'),
        Binding('x', 'stop_hunt', 'stop'),
        Binding('q', 'quit_app', 'close'),
        Binding(
            'ctrl+c',
            'quit_app',
            'back',
            show=False,
            priority=True,
        ),
        Binding(
            'escape',
            'quit_app',
            'back',
            show=False,
            priority=True,
        ),
    ]

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.sub_title = f'Hunt {_safe(session.hunt_id, 48)} · unified operator view'
        self._view_locks = {
            view: asyncio.Lock() for view in HUNT_OPEN_VIEWS
        }
        self._render_locks = {
            view: asyncio.Lock() for view in HUNT_OPEN_VIEWS
        }
        self._context_selection_lock = asyncio.Lock()
        self._chat_selection_lock = asyncio.Lock()
        self._active_refresh_task = None
        self._refresh_modal = None
        self._loading_view = None
        self._spinner_index = 0
        self._background_tasks = set()

    def compose(self) -> ComposeResult:
        yield Static(id='hunt-header')
        yield Tabs(
            *(Tab(HUNT_OPEN_LABELS[view], id=f'view-{view}') for view in HUNT_OPEN_VIEWS),
            active=f'view-{self.session.active_view}',
            id='hunt-tabs',
        )
        with Vertical(id='body'):
            with VerticalScroll(id='view-scroll'):
                yield Static(id='view-content')
            yield Input(id='steering')
            yield Static(id='operator-status')
        yield Footer()

    async def on_mount(self):
        self._render_state()
        self.set_interval(
            HUNT_OPEN_SPINNER_INTERVAL_SECONDS,
            self._advance_loading_spinner,
        )
        self.query_one('#hunt-tabs', Tabs).focus()

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
        self.session.notice = f'Background operation failed: {_safe(error, 240)}'
        if self.is_running:
            self._render_operator_status()

    @on(Tabs.TabActivated, '#hunt-tabs')
    def _tab_activated(self, event):
        if not event.tab.id:
            return
        view = event.tab.id.removeprefix('view-')
        requested_chat_id = (
            self.session.chat_session.requested_id
            if view == 'chat'
            else None
        )
        if (
            view == self.session.active_view
            and view in self.session.loaded_views
        ):
            if requested_chat_id:
                self._start_background_task(
                    self._select_embedded_conversation(requested_chat_id)
                )
            else:
                self._render_state()
            return
        self._cancel_active_refresh()
        self.session.select_view(view)
        if view in self.session.loaded_views:
            if requested_chat_id:
                self._start_background_task(
                    self._select_embedded_conversation(requested_chat_id)
                )
            else:
                self._render_state()
                self.call_after_refresh(self._scroll_to_top)
            return
        self._start_active_refresh()

    @on(Input.Submitted, '#steering')
    def _steer(self, event):
        message = event.value
        if not message.strip():
            return
        if not self.session.chat_session.can_guide:
            self.session.notice = 'Guidance is available only for the active root iteration.'
            self._render_state()
            return
        composer = self.query_one('#steering', Input)
        composer.disabled = True
        self._cancel_active_refresh()
        self._set_loading('chat')
        self._start_background_task(
            self._steer_in_background(message, composer)
        )

    async def _steer_in_background(self, message, composer):
        try:
            async with self._view_locks['chat']:
                await run_in_worker(
                    self.session.chat_session.send_guidance,
                    message,
                )
                await run_in_worker(self.session.refresh, 'chat')
        except Exception as exc:
            self.session.notice = f'Unable to queue guidance: {_safe(exc, 240)}'
        else:
            composer.value = ''
            self.session.notice = 'Guidance queued for the active root iteration.'
        finally:
            if self.is_running and self._loading_view == 'chat':
                self._clear_loading()
        if self.is_running and self.session.active_view == 'chat':
            self._render_state()

    def _start_active_refresh(self):
        task = self._active_refresh_task
        if task is not None and not task.done():
            return task
        task = self._start_background_task(self._refresh_active())
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

    async def _refresh_active(self):
        view = self.session.active_view
        lock = self._view_locks[view]
        if lock.locked():
            return

        self._set_loading(view)
        try:
            async with lock:
                await run_in_worker(
                    self.session.refresh,
                    view,
                )
        finally:
            if self.is_running and self._loading_view == view:
                self._clear_loading()
        if not self.is_running or self.session.active_view != view:
            return

        self._render_state()
        self.call_after_refresh(self._scroll_to_top)

    def _scroll_to_top(self):
        self.query_one('#view-scroll', VerticalScroll).scroll_home(
            animate=False,
        )

    async def _select_embedded_conversation(self, conversation_id):
        view = 'chat'
        if self._chat_selection_lock.locked():
            return
        self._set_loading(view)
        try:
            async with self._chat_selection_lock:
                selected = await run_in_worker(
                    self.session.chat_session.select_conversation,
                    conversation_id,
                )
            self.session.chat_session.requested_id = None
            if selected:
                self.session.invalidate_view(view)
                await self._rebuild_and_render(view)
            else:
                self.session.notice = 'Unable to select the workflow conversation.'
                self._render_state()
        finally:
            if self._loading_view == view:
                self._clear_loading()

    async def _refresh_view(self, view):
        async with self._view_locks[view]:
            return await run_in_worker(self.session.refresh, view)

    def _set_loading(self, view):
        self._loading_view = view
        self._spinner_index = 0
        self._update_tab_labels()
        self._render_operator_status()

    def _clear_loading(self):
        self._loading_view = None
        self._update_tab_labels()
        if self.is_running:
            self._render_operator_status()

    def _advance_loading_spinner(self):
        if self._loading_view is None:
            return
        self._spinner_index = (
            self._spinner_index + 1
        ) % len(HUNT_OPEN_SPINNER_FRAMES)
        self._update_tab_labels()
        self._render_operator_status()

    def _update_tab_labels(self):
        for view in HUNT_OPEN_VIEWS:
            label = HUNT_OPEN_LABELS[view]
            if view == self._loading_view:
                label += f' {HUNT_OPEN_SPINNER_FRAMES[self._spinner_index]}'
            self.query_one(f'#view-{view}', Tab).label = label

    def _render_state(self):
        self._update_tab_labels()
        self.query_one('#hunt-header', Static).update(
            build_hunt_open_header(self.session)
        )
        self.query_one('#view-content', Static).update(self.session.render())
        steering = self.query_one('#steering', Input)
        steering.display = self.session.active_view == 'chat'
        steering.disabled = not self.session.chat_session.can_guide
        steering.placeholder = (
            'Guide the active root iteration, then press Enter'
            if self.session.chat_session.can_guide
            else 'Read-only: select the active root iteration to steer'
        )
        self._render_operator_status()

    def _render_operator_status(self):
        status = Text()
        if self._loading_view is not None:
            view_label = HUNT_OPEN_LABELS[self._loading_view].split(' ', 1)[1]
            frame = HUNT_OPEN_SPINNER_FRAMES[self._spinner_index]
            status.append(f'{frame} Loading {view_label}…', style='cyan')
        else:
            pending = len(self.session.pending_interactions)
            error = self.session.view_errors.get(self.session.active_view)
            if error:
                status.append(f'⚠ {error}', style='yellow')
            elif pending:
                status.append(
                    f'⚠ {pending} pending interaction(s) · 7 or i to review safely',
                    style='yellow',
                )
            elif self.session.interaction_warning:
                status.append(self.session.interaction_warning, style='yellow')
            else:
                status.append(self._view_action_hint(), style='dim')
        self.query_one('#operator-status', Static).update(status)

    def _view_action_hint(self):
        view_hint = {
            'overview': 'r refresh',
            'vulnerabilities': '↑/↓ select · r refresh',
            'workflow': '↑/↓ select · Enter choose/show chat · Space collapse',
            'log': 'r refresh',
            'memory': '↑/↓ select · Enter/m editor · n new',
            'chat': '↑/↓ select · Enter/c live chat',
            'approvals': 'Enter/i review pending interactions',
        }[self.session.active_view]
        return f'←/→ or 1-7 views · {view_hint} · Esc back'

    def _activate(self, view):
        self.query_one('#hunt-tabs', Tabs).active = f'view-{view}'

    def action_previous_view(self):
        steering = self.query_one('#steering', Input)
        if steering.has_focus:
            steering.action_cursor_left()
            return
        index = HUNT_OPEN_VIEWS.index(self.session.active_view)
        self._activate(HUNT_OPEN_VIEWS[(index - 1) % len(HUNT_OPEN_VIEWS)])

    def action_next_view(self):
        steering = self.query_one('#steering', Input)
        if steering.has_focus:
            steering.action_cursor_right()
            return
        index = HUNT_OPEN_VIEWS.index(self.session.active_view)
        self._activate(HUNT_OPEN_VIEWS[(index + 1) % len(HUNT_OPEN_VIEWS)])

    def action_view_1(self): self._activate(HUNT_OPEN_VIEWS[0])
    def action_view_2(self): self._activate(HUNT_OPEN_VIEWS[1])
    def action_view_3(self): self._activate(HUNT_OPEN_VIEWS[2])
    def action_view_4(self): self._activate(HUNT_OPEN_VIEWS[3])
    def action_view_5(self): self._activate(HUNT_OPEN_VIEWS[4])
    def action_view_6(self): self._activate(HUNT_OPEN_VIEWS[5])
    def action_view_7(self): self._activate(HUNT_OPEN_VIEWS[6])

    def action_context_up(self):
        self._start_background_task(self._move_context(-1))

    def action_context_down(self):
        self._start_background_task(self._move_context(1))

    async def _move_context(self, delta):
        view = self.session.active_view
        if view == 'memory':
            if self._context_selection_lock.locked():
                return
            self._set_loading(view)
            try:
                async with self._context_selection_lock:
                    moved = await run_in_worker(
                        self.session.move_context_cursor,
                        delta,
                    )
                if moved:
                    await self._rebuild_and_render(view, delta)
            finally:
                if self._loading_view == view:
                    self._clear_loading()
            return
        if view == 'chat':
            if self._chat_selection_lock.locked():
                return
            self._set_loading(view)
            try:
                async with self._chat_selection_lock:
                    moved = await run_in_worker(
                        self.session.chat_session.move_selection,
                        delta,
                    )
                if moved:
                    self.session.invalidate_view('chat')
                    await self._rebuild_and_render(view, delta)
            finally:
                if self._loading_view == view:
                    self._clear_loading()
            return
        if self.session.move_context_cursor(delta):
            self._render_interactive_state(delta)

    def _render_interactive_state(self, scroll_delta=0):
        view = self.session.active_view
        self._start_background_task(
            self._rebuild_and_render(view, scroll_delta)
        )

    async def _rebuild_and_render(self, view, scroll_delta=0):
        async with self._render_locks[view]:
            await run_in_worker(self.session.rebuild_view, view)
        if self.is_running and self.session.active_view == view:
            self._render_state()
            if scroll_delta:
                self.call_after_refresh(
                    self._scroll_content,
                    scroll_delta,
                )

    def _scroll_content(self, delta):
        self.query_one('#view-scroll', VerticalScroll).scroll_relative(
            y=delta,
            animate=False,
        )

    def action_activate_context(self):
        action = {
            'memory': self.action_memory_editor,
            'workflow': self._activate_workflow_context,
            'chat': self.action_live_chat,
            'approvals': self.action_review_approvals,
        }.get(self.session.active_view)
        if action is not None:
            action()

    def action_toggle_context(self):
        browser = self.session.workflow_browser
        if self.session.active_view == 'workflow' and browser is not None:
            browser.toggle()
            self.session.invalidate_view('workflow')
            self._render_interactive_state()

    def action_force_refresh(self):
        if self._refresh_modal is not None:
            return
        task = self._active_refresh_task
        if task is not None and not task.done():
            return
        view = self.session.active_view
        view_name = HUNT_OPEN_LABELS[view].split(' ', 1)[1]
        modal = RefreshModal(
            view_name,
            lambda: self._refresh_view(view),
        )
        self._refresh_modal = modal
        self.push_screen(
            modal,
            lambda result: self._manual_refresh_finished(
                view,
                modal,
                result,
            ),
        )

    def _manual_refresh_finished(self, view, modal, result: RefreshResult):
        if self._refresh_modal is modal:
            self._refresh_modal = None
        if not isinstance(result, RefreshResult):
            return
        if result.error is not None:
            self.session.notice = (
                f'Unable to refresh {view}: {_safe(result.error, 240)}'
            )
        if self.is_running and self.session.active_view == view:
            self._render_state()

    def action_memory_editor(self):
        if self.session.active_view == 'memory':
            self.exit(result='memory')
        else:
            self._activate('memory')

    def action_new_memory(self):
        if self.session.active_view == 'memory':
            self.exit(result='memory-new')
        else:
            self._activate('memory')

    def action_live_chat(self):
        if self.session.active_view == 'workflow':
            self._activate_workflow_context()
        elif self.session.active_view == 'chat':
            self._request_chat(self.session.chat_session.selected_id)
        else:
            self._activate('chat')

    def _activate_workflow_context(self):
        browser = self.session.workflow_browser
        if browser is None:
            return
        conversation_id = browser.enter()
        self.session.invalidate_view('workflow')
        if conversation_id:
            self.session.chat_session.requested_id = conversation_id
            self._activate('chat')
        else:
            self._render_interactive_state()

    def _request_chat(self, conversation_id):
        if not conversation_id:
            self.session.notice = 'Select a Hunt conversation first.'
            self._render_state()
            return
        self.session.requested_chat_id = conversation_id
        self.exit(result='chat')

    def action_review_approvals(self):
        if self.session.active_view != 'approvals':
            self._activate('approvals')
        elif self.session.pending_interactions:
            self.exit(result='approvals')
        else:
            self.session.notice = 'There are no pending Hunt interactions.'
            self._render_state()

    def action_pause_hunt(self):
        if self.session.status != 'active':
            self._reject_lifecycle('pause')
            return
        self.exit(result='pause')

    def action_resume_hunt(self):
        if self.session.status != 'paused':
            self._reject_lifecycle('resume')
            return
        self.exit(result='resume')

    def action_stop_hunt(self):
        if self.session.status not in ('active', 'paused'):
            self._reject_lifecycle('stop')
            return
        self.exit(result='stop')

    def _reject_lifecycle(self, action):
        self.session.notice = (
            f'Hunt {self.session.hunt_id} cannot {action} while '
            f'{self.session.status}.'
        )
        self._render_state()

    def action_quit_app(self):
        browser = self.session.workflow_browser
        if (
            self.session.active_view == 'workflow'
            and browser is not None
            and browser.leave_steps()
        ):
            self.session.invalidate_view('workflow')
            self._render_interactive_state()
            return
        self.exit(result='close')


def run_hunt_open(
    sdk,
    hunt_id,
    *,
    console=None,
    initial_hunt=None,
    authorize_hunt=None,
    confirm_stop=None,
    review_interactions=None,
    app_factory=HuntOpenApp,
    live_chat_runner=run_live_hunt_chat,
    memory_browser=browse_hunt_memory,
):
    """Run the unified app, suspending it for shared secure sub-interfaces."""
    if not supports_fullscreen_hunt_open():
        raise ValueError('hunt open requires an interactive terminal')

    session = HuntOpenSession(
        sdk,
        hunt_id,
        initial_hunt=initial_hunt,
        authorize_hunt=authorize_hunt,
    )
    with _loading_feedback(console, 'Loading Hunt overview…'):
        session.refresh('overview', raise_errors=True)

    shared_http = install_shared_aiohttp_session(sdk)
    try:
        return _run_hunt_open_loop(
            session,
            sdk,
            console=console,
            authorize_hunt=authorize_hunt,
            confirm_stop=confirm_stop,
            review_interactions=review_interactions,
            app_factory=app_factory,
            live_chat_runner=live_chat_runner,
            memory_browser=memory_browser,
        )
    finally:
        shared_http.close()


def _run_hunt_open_loop(
    session,
    sdk,
    *,
    console,
    authorize_hunt,
    confirm_stop,
    review_interactions,
    app_factory,
    live_chat_runner,
    memory_browser,
):
    while True:
        try:
            outcome = app_factory(session).run()
        except KeyboardInterrupt:
            break
        if outcome in (None, 'close'):
            break
        if outcome in ('memory', 'memory-new'):
            with _loading_feedback(console, 'Opening Hunt memory…'):
                session.revalidate()
            if outcome == 'memory-new':
                memory_browser(
                    console,
                    sdk.hunts,
                    session.hunt_id,
                    start_new=True,
                )
            else:
                memory_browser(console, sdk.hunts, session.hunt_id)
            with _loading_feedback(console, 'Refreshing Hunt memory…'):
                session.refresh('memory')
            continue
        if outcome == 'chat':
            selected_id = (
                session.requested_chat_id
                or session.chat_session.selected_id
                or None
            )
            session.requested_chat_id = None
            chat_session = live_chat_runner(
                sdk,
                session.hunt_id,
                requested_id=selected_id,
                request_pages=HUNT_OPEN_REFRESH_MAX_PAGES,
                authorize_hunt=authorize_hunt,
                review_interactions=review_interactions,
                console=console,
            )
            if isinstance(chat_session, HuntChatSession):
                session.chat_session = chat_session
                session.pending_interactions = list(
                    chat_session.pending_interactions
                )
                session.loaded_views.add('chat')
                session.rebuild_view('chat')
            continue
        if outcome == 'approvals':
            with _loading_feedback(console, 'Loading approvals…'):
                session.revalidate()
            if review_interactions is None:
                session.notice = (
                    'Use the Hunt interactions command to answer requests.'
                )
            else:
                review_interactions(list(session.pending_interactions))
                with _loading_feedback(console, 'Refreshing approvals…'):
                    session.refresh('approvals')
            continue
        if outcome == 'stop':
            with _loading_feedback(console, 'Checking Hunt state…'):
                session.revalidate()
            confirmer = confirm_stop or (lambda _message: False)
            if not confirmer(
                f'Stop Hunt {session.hunt_id} permanently?'
            ):
                session.notice = 'Stop cancelled.'
                continue
        if outcome in ('pause', 'resume', 'stop'):
            action_label = {
                'pause': 'Pausing',
                'resume': 'Resuming',
                'stop': 'Stopping',
            }[outcome]
            try:
                with _loading_feedback(
                    console,
                    f'{action_label} Hunt…',
                ):
                    session.perform_lifecycle(outcome)
                    session.refresh(session.active_view)
            except Exception as exc:
                session.notice = f'Unable to {outcome} Hunt: {_safe(exc, 300)}'
            continue
    return session


def _loading_feedback(console, message):
    if console is None:
        return nullcontext()
    return console.status(message, spinner='dots')


def _finding_key(record):
    if not isinstance(record, dict):
        return ''
    risk = record.get('risk') if isinstance(record.get('risk'), dict) else record
    return str(risk.get('key') or risk.get('id') or '')


def _workflow_key(record):
    if not isinstance(record, dict):
        return ''
    return str(record.get('run_id') or record.get('uuid') or record.get('key') or '')


def _restored_index(records, selected_key, key, fallback):
    if selected_key:
        for index, record in enumerate(records):
            if key(record) == selected_key:
                return index
    if not records:
        return 0
    return min(max(int(fallback or 0), 0), len(records) - 1)


def _safe(value, limit):
    printable = ''.join(
        character if character in '\n\t' or character.isprintable() else ' '
        for character in str(value or '')
    )
    return printable[:limit]
