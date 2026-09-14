import json
import sys
from datetime import datetime
from io import StringIO

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


STATUS_PRESENTATION = {
    'pending': ('○', 'dim'),
    'queued': ('◷', 'cyan'),
    'running': ('●', 'yellow'),
    'persisting': ('●', 'yellow'),
    'completed': ('✓', 'green'),
    'done': ('✓', 'green'),
    'failed': ('✗', 'red'),
    'skipped': ('−', 'dim'),
}
TERMINAL_STATUSES = {'completed', 'done', 'failed', 'skipped'}
KIND_PRESENTATION = {
    'agent': ('◆', 'magenta'),
    'capability': ('⚡', 'cyan'),
    'func': ('ƒ', 'blue'),
    'expansion': ('⋈', 'bright_magenta'),
    'gate': ('◇', 'bright_black'),
}


def build_hunt_workflows(records):
    """Build a visual Hunt workflow dashboard as Rich renderables."""
    runs = _sorted_runs(records)
    if not runs:
        return Panel(
            Text('No workflow runs found for this Hunt.', style='dim'),
            title='Hunt workflows',
            border_style='dim',
            box=box.ROUNDED,
        )

    overview = _overview_panel(runs)
    iterations = [
        _iteration_panel(run, len(runs) - index)
        for index, run in enumerate(runs)
    ]
    return Group(overview, Text(''), *iterations)


def browse_hunt_workflows(console, records):
    """Open an interactive workflow browser, or print when no TTY exists."""
    runs = _sorted_runs(records)
    if not _supports_fullscreen_browser():
        console.print(build_hunt_workflows(runs))
        return
    if not runs:
        console.print(build_hunt_workflows(runs))
        return
    _run_workflow_browser(console, WorkflowBrowser(runs))


class WorkflowBrowser:
    """Keyboard navigation and expansion state for Hunt workflow runs."""

    page_size = 8

    def __init__(self, runs):
        self.runs = list(runs)
        self.cursor = 0
        self.expanded = {0} if self.runs else set()

    @property
    def current(self):
        return self.runs[self.cursor] if self.runs else None

    @property
    def visible_start(self):
        return (self.cursor // self.page_size) * self.page_size

    @property
    def visible_runs(self):
        start = self.visible_start
        return self.runs[start:start + self.page_size]

    @property
    def current_is_expanded(self):
        return self.cursor in self.expanded

    def move(self, delta):
        if not self.runs:
            return
        self.cursor = min(max(self.cursor + delta, 0), len(self.runs) - 1)

    def toggle(self):
        if self.cursor in self.expanded:
            self.expanded.remove(self.cursor)
        else:
            self.expanded.add(self.cursor)

    def expand(self):
        self.expanded.add(self.cursor)

    def collapse(self):
        self.expanded.discard(self.cursor)

    def iteration_number(self, index=None):
        index = self.cursor if index is None else index
        return len(self.runs) - index


def _supports_fullscreen_browser():
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def _run_workflow_browser(console, browser):
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    key_bindings = KeyBindings()

    @key_bindings.add('up')
    def _move_up(event):
        browser.move(-1)

    @key_bindings.add('down')
    def _move_down(event):
        browser.move(1)

    @key_bindings.add('pageup')
    def _page_up(event):
        browser.move(-browser.page_size)

    @key_bindings.add('pagedown')
    def _page_down(event):
        browser.move(browser.page_size)

    @key_bindings.add('home')
    def _first(event):
        browser.cursor = 0

    @key_bindings.add('end')
    def _last(event):
        browser.cursor = len(browser.runs) - 1

    @key_bindings.add(' ')
    def _toggle(event):
        browser.toggle()

    @key_bindings.add('right')
    def _expand(event):
        browser.expand()

    @key_bindings.add('left')
    def _collapse(event):
        browser.collapse()

    @key_bindings.add('q')
    @key_bindings.add('escape')
    @key_bindings.add('c-c')
    @key_bindings.add('enter')
    def _close(event):
        event.app.exit()

    def display():
        output = StringIO()
        render_console = Console(
            file=output,
            force_terminal=True,
            width=max(80, getattr(console, 'width', 80)),
        )
        render_console.print(
            '↑/↓ move  SPACE expand/collapse  ←/→ collapse/expand  '
            'PgUp/PgDn jump  ENTER/q/ESC close',
            style='dim',
        )
        render_console.print(_workflow_navigation_table(browser))
        if browser.current_is_expanded:
            render_console.print(_iteration_panel(
                browser.current,
                browser.iteration_number(),
            ))
        else:
            render_console.print(
                'Press Space to expand the highlighted workflow.',
                style='dim',
            )
        return ANSI(output.getvalue())

    application = Application(
        layout=Layout(Window(content=FormattedTextControl(display))),
        key_bindings=key_bindings,
        full_screen=True,
    )
    application.run()


def _workflow_navigation_table(browser):
    table = Table(
        title=Text('Hunt workflow iterations', style='bold cyan'),
        box=box.ROUNDED,
        border_style='cyan',
        expand=True,
        header_style='bold',
    )
    table.add_column('', width=3)
    table.add_column('ITERATION', width=11)
    table.add_column('WORKFLOW', min_width=20, ratio=3)
    table.add_column('STATUS', width=12)
    table.add_column('STARTED', min_width=18, ratio=1)
    start = browser.visible_start
    for visible_index, run in enumerate(browser.visible_runs):
        index = start + visible_index
        status = _shown_status(run.get('status'))
        symbol, style = _status_presentation(status)
        marker = '▶' if index == browser.cursor else ' '
        disclosure = '▾' if index in browser.expanded else '▸'
        table.add_row(
            Text(f'{marker}{disclosure}', style='bold cyan'),
            Text(str(browser.iteration_number(index))),
            Text(
                _safe(run.get('title') or run.get('definition') or 'workflow', 100),
                style='bold',
            ),
            Text(f'{symbol} {status.upper()}', style=style),
            Text(_format_timestamp(run.get('created')), style='dim'),
        )
    return table


def format_hunt_workflows(records, width=140):
    """Render the dashboard without ANSI color for tests and plain consumers."""
    output = StringIO()
    console = Console(
        file=output,
        width=width,
        force_terminal=False,
        color_system=None,
    )
    console.print(build_hunt_workflows(records))
    return output.getvalue().rstrip()


def _sorted_runs(records):
    return sorted(
        (record for record in records or [] if isinstance(record, dict)),
        key=lambda record: _timestamp_sort_key(record.get('created')),
        reverse=True,
    )


def _overview_panel(runs):
    status_counts = {}
    for run in runs:
        status = _shown_status(run.get('status'))
        status_counts[status] = status_counts.get(status, 0) + 1

    summary = Text('STATUS  ', style='bold bright_black')
    for status in ('running', 'queued', 'completed', 'failed'):
        count = status_counts.get(status, 0)
        if not count:
            continue
        symbol, style = _status_presentation(status)
        if len(summary) > 8:
            summary.append('   ')
        summary.append(f'{symbol} {count} {status.upper()}', style=f'bold {style}')

    active = status_counts.get('running', 0) + status_counts.get('queued', 0)
    findings = sum(_number(run.get('total_finding_count')) for run in runs)
    metrics = Columns(
        [
            _metric_panel('ITERATIONS', len(runs), 'cyan'),
            _metric_panel('ACTIVE', active, 'yellow'),
            _metric_panel('FINDINGS', findings, 'green'),
        ],
        equal=True,
        expand=True,
        padding=(0, 1),
    )

    return Panel(
        Group(Align.center(summary), Text(''), metrics),
        title=Text('⚔  Hunt workflow timeline  ⚔', style='bold cyan'),
        subtitle=Text('HANNIBAL · AUTONOMOUS SECURITY OPERATIONS', style='dim'),
        border_style='bright_cyan',
        box=box.HEAVY,
        padding=(1, 2),
    )


def _metric_panel(label, value, style):
    metric = Text()
    metric.append(f'{value}\n', style=f'bold {style}')
    metric.append(label, style='dim')
    return Panel(
        Align.center(metric),
        border_style=style,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _iteration_panel(run, iteration):
    status = _shown_status(run.get('status'))
    symbol, style = _status_presentation(status)
    title = Text()
    title.append(f'Iteration {iteration}  ', style='bold')
    title.append(f'{symbol} {status.upper()}', style=f'bold {style}')

    body = Group(
        _run_metadata(run),
        Text(''),
        _progress_line(run.get('steps')),
        _pipeline_rail(run.get('steps')),
        Text(''),
        _steps_table(run.get('steps')),
    )
    return Panel(
        body,
        title=title,
        subtitle=Text(_format_timestamp(run.get('created')), style='dim'),
        border_style=style,
        box=box.ROUNDED,
        padding=(1, 1),
    )


def _run_metadata(run):
    metadata = Table.grid(expand=True, padding=(0, 2))
    metadata.add_column(style='dim', width=10)
    metadata.add_column(style='white')
    metadata.add_column(style='dim', width=10)
    metadata.add_column(style='white')

    metadata.add_row(
        'Workflow',
        Text(
            _safe(run.get('title') or run.get('definition') or 'workflow', 80),
            style='bold',
        ),
        'Run ID',
        Text(_safe(run.get('run_id') or 'unknown', 80), style='cyan'),
    )
    endpoint = (
        _safe(run.get('endpoint_id'), 100)
        if run.get('endpoint_required')
        else 'external compute'
    )
    metadata.add_row('Execution', endpoint, 'Totals', _run_totals(run))
    return metadata


def _run_totals(run):
    totals = []
    if run.get('total_tokens_spent'):
        totals.append(f'{run["total_tokens_spent"]} tokens')
    if run.get('total_finding_count'):
        totals.append(f'{run["total_finding_count"]} findings')
    if run.get('total_result_count'):
        totals.append(f'{run["total_result_count"]} results')
    return ', '.join(totals) or '—'


def _progress_line(steps):
    steps = [step for step in steps or [] if isinstance(step, dict)]
    total = len(steps)
    completed = sum(
        1 for step in steps
        if _shown_status(step.get('status')) in TERMINAL_STATUSES
    )
    width = 28
    filled = round(width * completed / total) if total else 0
    percentage = round(100 * completed / total) if total else 0

    progress = Text('PROGRESS  ', style='bold bright_black')
    progress.append('█' * filled, style='green')
    progress.append('░' * (width - filled), style='bright_black')
    progress.append(f'  {completed}/{total}  {percentage}%', style='bold')

    current = next(
        (
            step for step in steps
            if _shown_status(step.get('status')) in {'running', 'queued'}
        ),
        None,
    )
    if current:
        progress.append('\nNOW       ', style='bold bright_black')
        progress.append(
            _safe(current.get('title') or current.get('name'), 100),
            style='bold yellow',
        )
    return progress


def _pipeline_rail(steps):
    steps = [step for step in steps or [] if isinstance(step, dict)]
    rail = Text('\nPIPELINE  ', style='bold bright_black')
    visible = steps[:8]
    for index, step in enumerate(visible):
        if index:
            rail.append(' ━ ', style='bright_black')
        status = _shown_status(step.get('status'))
        symbol, style = _status_presentation(status)
        short_title = _short(step.get('title') or step.get('name') or '?', 14)
        rail.append(f'{symbol} {short_title}', style=style)
    if len(steps) > len(visible):
        rail.append(f' ━ +{len(steps) - len(visible)}', style='dim')
    return rail


def _steps_table(steps):
    steps = [step for step in steps or [] if isinstance(step, dict)]
    table = Table(
        box=box.SIMPLE_HEAVY,
        expand=True,
        show_edge=False,
        header_style='bold bright_black',
        padding=(0, 1),
    )
    table.add_column('STEP', min_width=18, ratio=2)
    table.add_column('STATUS', width=12, no_wrap=True)
    table.add_column('ACTIVITY', min_width=16, ratio=3)
    table.add_column('METRICS', width=14, no_wrap=True)

    if not steps:
        table.add_row(Text('No workflow steps recorded.', style='dim'), '', '', '')
        return table

    for step in steps:
        status = _shown_status(step.get('status'))
        symbol, style = _status_presentation(status)
        title = _safe(step.get('title') or step.get('name') or 'unnamed step', 100)
        if step.get('expanded_by'):
            title = f'↳ {title}'
        activity = _step_summary(step)
        if step.get('error'):
            activity = f'Error: {_safe(step.get("error"), 160)}'

        kind = _safe(step.get('kind') or 'capability', 32).lower()
        kind_symbol, kind_style = KIND_PRESENTATION.get(kind, ('•', 'white'))
        step_label = Text(title, style='bold white' if status == 'running' else 'white')
        step_label.append(
            f'\n{kind_symbol} {kind.upper()}',
            style=kind_style,
        )
        state = Text(f'{symbol} {status.upper()}', style=f'bold {style}')
        table.add_row(
            step_label,
            state,
            Text(activity or '—', style='red' if step.get('error') else 'dim'),
            Text(_step_metrics(step), style='dim'),
            style='on grey11' if status == 'running' else None,
        )
    return table


def _shown_status(value):
    status = _safe(value or 'unknown', 32).lower()
    return 'running' if status == 'persisting' else status


def _status_presentation(status):
    return STATUS_PRESENTATION.get(status, ('?', 'white'))


def _step_metrics(step):
    metrics = []
    duration = _step_duration(step)
    if duration:
        metrics.append(duration)
    if step.get('tokens_spent'):
        metrics.append(f'{step["tokens_spent"]} tokens')
    return ' · '.join(metrics) or '—'


def _step_summary(step):
    output = step.get('output')
    if not output:
        return ''
    try:
        parsed = json.loads(output) if isinstance(output, str) else output
    except (TypeError, ValueError):
        parsed = output

    name = step.get('name') or ''
    if name in ('inject-memory-context', 'inject-cloud-memory-context'):
        memory = parsed.get('memory') if isinstance(parsed, dict) else None
        items = memory.get('items', []) if isinstance(memory, dict) else []
        if not items:
            return 'empty memory'
        counts = memory.get('status_counts') or {}
        if not isinstance(counts, dict) or not counts:
            return f'{len(items)} memory items'
        labels = ', '.join(f'{value} {key}' for key, value in counts.items())
        return _safe(f'{len(items)} memory items ({labels})', 160)

    if name == 'target-selection' and isinstance(parsed, dict):
        target = parsed.get('target_dns')
        return _safe(f'Selected {target}', 160) if target else ''

    if name in ('dispatch-planning', 'plan-cloud-iteration'):
        dispatches = parsed.get('agents') if isinstance(parsed, dict) else None
        return _dispatch_names(dispatches)

    if name in ('extract-dispatches', 'extract-cloud-dispatches'):
        if isinstance(parsed, list) and parsed:
            suffix = '' if len(parsed) == 1 else 'es'
            return f'{len(parsed)} dispatch{suffix}'
        return ''

    if name in ('summarize-iteration', 'summarize-cloud-iteration'):
        if not isinstance(parsed, dict) or parsed.get('findings_count') is None:
            return ''
        agents = parsed.get('agents_dispatched') or []
        return f'{parsed["findings_count"]} findings, {len(agents)} agents'

    if step.get('expanded_by') and isinstance(parsed, str):
        first = parsed.strip(' "\'').splitlines()[0].split('.')[0].strip()
        return _safe(first, 80) if len(first) >= 5 else ''
    return ''


def _dispatch_names(dispatches):
    if not isinstance(dispatches, list) or not dispatches:
        return ''
    names = [
        str(dispatch.get('agent', '')).removesuffix('-agent')
        for dispatch in dispatches
        if isinstance(dispatch, dict) and dispatch.get('agent')
    ]
    if len(names) <= 3:
        return _safe(', '.join(names), 160)
    return _safe(f'{", ".join(names[:3])} +{len(names) - 3}', 160)


def _step_duration(step):
    start = _timestamp_value(step.get('queued_at'))
    end = _timestamp_value(step.get('completed_at'))
    if start is None or end is None or end < start:
        return ''
    seconds = int((end - start).total_seconds())
    if seconds < 60:
        return f'{seconds}s'
    return f'{seconds // 60}m {seconds % 60}s'


def _format_timestamp(value):
    parsed = _timestamp_value(value)
    if parsed is None:
        return ''
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


def _number(value):
    return value if isinstance(value, (int, float)) else 0



def _short(value, limit):
    text = _safe(value, limit + 1)
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _safe(value, limit):
    if value is None:
        return ''
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in str(value)
    )
    return ' '.join(printable.split())[:limit]
