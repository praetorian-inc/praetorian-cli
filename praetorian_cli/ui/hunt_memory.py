import re
import sys
from io import StringIO

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from praetorian_cli.ui.hunt_data import build_hunt_memory


SUMMARY_LOG_TITLE = 'summary.log'
MEMORY_REFRESH_MAX_PAGES = 10
MEMORY_VISIBLE_ITEMS = 16
_MEMORY_TITLE = re.compile(r'[a-zA-Z0-9._\- ]{1,128}')


class HuntMemoryBrowser:
    """State and Hunt-owned mutations for the fullscreen memory browser."""

    def __init__(self, hunts, hunt_id, items=None, next_offset=None):
        self.hunts = hunts
        self.hunt_id = hunt_id
        self.items = []
        self.cursor = 0
        self.content = ''
        self.mode = 'browse'
        self.edit_title = None
        self.original_content = ''
        self.draft = ''
        self.new_item = False
        self.confirm_action = None
        self.confirm_return_mode = 'browse'
        self.status = ''
        self.more_available = bool(next_offset)
        self._replace_items(items or [])

    @property
    def current(self):
        if 0 <= self.cursor < len(self.items):
            return self.items[self.cursor]
        return None

    @property
    def current_title(self):
        current = self.current
        return _item_title(current) if current else None

    @property
    def dirty(self):
        return bool(
            self.edit_title is not None
            and (self.new_item or self.draft != self.original_content)
        )

    @property
    def visible_start(self):
        return (self.cursor // MEMORY_VISIBLE_ITEMS) * MEMORY_VISIBLE_ITEMS

    @property
    def visible_items(self):
        start = self.visible_start
        return self.items[start:start + MEMORY_VISIBLE_ITEMS]

    @property
    def confirmation_message(self):
        if self.confirm_action == 'delete':
            return f'Delete {self.current_title!r}? This cannot be undone. (y/N)'
        if self.confirm_action == 'quit':
            return 'Discard unsaved changes and close the memory browser? (y/N)'
        if self.confirm_action == 'discard':
            return 'Discard unsaved changes? (y/N)'
        return ''

    def load_current(self):
        title = self.current_title
        if title is None:
            self.content = ''
            return True
        try:
            content = self.hunts.get_memory(self.hunt_id, title)
        except Exception as exc:
            self.content = ''
            self.status = f'Unable to load {title}: {exc}'
            return False
        self.content = str(content or '')
        self.status = ''
        return True

    def move(self, delta):
        if self.mode != 'browse' or not self.items:
            return False
        next_cursor = min(max(self.cursor + delta, 0), len(self.items) - 1)
        if next_cursor == self.cursor:
            return False
        self.cursor = next_cursor
        self.load_current()
        return True

    def select_first(self):
        return self._select_index(0)

    def select_last(self):
        return self._select_index(len(self.items) - 1)

    def refresh(self):
        """Reload a bounded number of pages while retaining the selected title."""
        if self.mode != 'browse':
            return False
        selected_title = self.current_title
        old_cursor = self.cursor
        try:
            items, next_offset = self.hunts.list_memory(
                self.hunt_id,
                pages=MEMORY_REFRESH_MAX_PAGES,
            )
        except Exception as exc:
            self.status = f'Unable to refresh memory: {exc}'
            return False

        self.more_available = bool(next_offset)
        self._replace_items(
            items,
            selected_title=selected_title,
            fallback_cursor=old_cursor,
        )
        loaded = self.load_current()
        if loaded:
            suffix = ' · additional items not loaded' if self.more_available else ''
            self.status = f'Refreshed {len(self.items)} memory items{suffix}.'
        return loaded

    def begin_edit(self):
        if self.mode != 'browse' or self.current_title is None:
            self.status = 'Select a memory item to edit.'
            return False
        if _is_summary_log(self.current_title):
            self.status = 'summary.log is system-owned and read-only.'
            return False
        self.edit_title = self.current_title
        self.original_content = self.content
        self.draft = self.content
        self.new_item = False
        self.mode = 'edit'
        self.status = 'Editing · Ctrl+S save · Esc finish'
        return True

    def begin_new(self, title):
        if self.mode != 'title':
            return False
        title = str(title or '').strip()
        error = _title_error(title)
        if error:
            self.status = error
            return False
        if any(_item_title(item) == title for item in self.items):
            self.status = f'Memory item {title!r} already exists.'
            return False
        self.edit_title = title
        self.original_content = ''
        self.draft = ''
        self.new_item = True
        self.mode = 'edit'
        self.status = 'New item · Ctrl+S save · Esc cancel'
        return True

    def request_new(self):
        if self.mode != 'browse':
            return False
        self.mode = 'title'
        self.status = 'Enter a title for the new memory item.'
        return True

    def cancel_title(self):
        if self.mode == 'title':
            self.mode = 'browse'
            self.status = 'New item cancelled.'

    def update_draft(self, value):
        if self.mode == 'edit':
            self.draft = str(value)

    def save(self):
        if self.mode != 'edit' or self.edit_title is None:
            return False
        title = self.edit_title
        try:
            self.hunts.save_memory(self.hunt_id, title, self.draft)
        except Exception as exc:
            self.status = f'Unable to save {title}: {exc}'
            return False

        if self.new_item:
            self.items.append({'title': title})
            self._replace_items(self.items, selected_title=title)
        self.content = self.draft
        self.original_content = self.draft
        self.edit_title = None
        self.new_item = False
        self.mode = 'browse'
        self.status = f'Saved {title}.'
        return True

    def request_delete(self):
        title = self.current_title
        if self.mode != 'browse' or title is None:
            self.status = 'Select a memory item to delete.'
            return False
        if _is_summary_log(title):
            self.status = 'summary.log is system-owned and read-only.'
            return False
        self._begin_confirmation('delete', 'browse')
        return True

    def request_finish_edit(self):
        if self.mode != 'edit':
            return False
        if self.dirty:
            self._begin_confirmation('discard', 'edit')
            return False
        self._discard_edit('Edit closed.')
        return True

    def request_quit(self):
        if self.mode == 'edit':
            if self.dirty:
                self._begin_confirmation('quit', 'edit')
                return False
            return True
        if self.mode == 'title':
            self.cancel_title()
            return False
        return self.mode == 'browse'

    def answer_confirmation(self, confirmed):
        """Apply y/n to a pending confirmation; return True when the app exits."""
        if self.mode != 'confirm':
            return False
        action = self.confirm_action
        return_mode = self.confirm_return_mode
        self.confirm_action = None
        self.confirm_return_mode = 'browse'

        if not confirmed:
            self.mode = return_mode
            self.status = 'Cancelled.'
            return False
        if action == 'quit':
            return True
        if action == 'discard':
            self._discard_edit('Changes discarded.')
            return False
        if action == 'delete':
            self.mode = 'browse'
            self._delete_current()
        return False

    def _begin_confirmation(self, action, return_mode):
        self.confirm_action = action
        self.confirm_return_mode = return_mode
        self.mode = 'confirm'
        self.status = self.confirmation_message

    def _discard_edit(self, status):
        self.edit_title = None
        self.original_content = ''
        self.draft = ''
        self.new_item = False
        self.mode = 'browse'
        self.status = status

    def _delete_current(self):
        title = self.current_title
        if title is None:
            return False
        old_cursor = self.cursor
        try:
            self.hunts.delete_memory(self.hunt_id, title)
        except Exception as exc:
            self.status = f'Unable to delete {title}: {exc}'
            return False

        self._replace_items(
            [item for item in self.items if _item_title(item) != title],
            fallback_cursor=old_cursor,
        )
        loaded = self.load_current()
        if loaded:
            self.status = f'Deleted {title}.'
        return loaded

    def _select_index(self, index):
        if self.mode != 'browse' or not self.items:
            return False
        index = min(max(index, 0), len(self.items) - 1)
        if self.cursor == index:
            return False
        self.cursor = index
        self.load_current()
        return True

    def _replace_items(
        self,
        items,
        selected_title=None,
        fallback_cursor=None,
    ):
        previous_cursor = self.cursor if fallback_cursor is None else fallback_cursor
        unique = {}
        for item in items or []:
            if not isinstance(item, dict):
                continue
            title = _item_title(item)
            if not title or _is_summary_log(title):
                continue
            unique.setdefault(title, {**item, 'title': title})
        self.items = sorted(
            unique.values(),
            key=lambda item: _item_title(item).casefold(),
        )
        titles = [_item_title(item) for item in self.items]
        if selected_title in titles:
            self.cursor = titles.index(selected_title)
        elif self.items:
            self.cursor = min(max(previous_cursor, 0), len(self.items) - 1)
        else:
            self.cursor = 0


def supports_fullscreen_memory_browser():
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def browse_hunt_memory(console, hunts, hunt_id):
    """Browse Hunt memory in a TTY, preserving static output for automation."""
    if not supports_fullscreen_memory_browser():
        items, _ = hunts.list_memory(hunt_id)
        console.print(build_hunt_memory(items))
        return False

    items, next_offset = hunts.list_memory(
        hunt_id,
        pages=MEMORY_REFRESH_MAX_PAGES,
    )
    browser = HuntMemoryBrowser(
        hunts,
        hunt_id,
        items,
        next_offset=next_offset,
    )
    browser.load_current()
    _run_memory_browser(console, browser)
    return True


def build_hunt_memory_navigation(browser):
    """Render the persistent memory-item list used by the fullscreen browser."""
    table = Table(
        title=Text(
            f'Hunt memory · {len(browser.items)} items',
            style='bold magenta',
        ),
        box=box.ROUNDED,
        border_style='magenta',
        expand=True,
        show_header=True,
        header_style='bold',
        padding=(0, 1),
    )
    table.add_column('', width=2, no_wrap=True)
    table.add_column('TITLE', min_width=12, ratio=2)
    table.add_column('UPDATED', min_width=10, ratio=1)
    start = browser.visible_start
    for visible_index, item in enumerate(browser.visible_items):
        index = start + visible_index
        selected = index == browser.cursor
        marker = '▶' if selected else ' '
        title = _item_title(item)
        if browser.edit_title == title and browser.dirty:
            title += ' *'
        table.add_row(
            Text(marker, style='bold cyan'),
            Text(title, style='bold white' if selected else 'white'),
            Text(_updated(item), style='dim'),
        )
    if not browser.items:
        table.add_row('', Text('No memory items yet.', style='dim'), '')
    return table


def build_hunt_memory_preview(browser):
    """Render the selected item's full multiline content."""
    title = browser.current_title
    if title is None:
        body = Text('Press n to create the first memory item.', style='dim')
        shown_title = 'Memory item'
    else:
        body = Text(_safe_multiline(browser.content) or ' ', style='white')
        shown_title = title
    return Panel(
        body,
        title=Text(f'◆ {shown_title}', style='bold magenta'),
        subtitle=Text('Read-only preview · Enter/e to edit', style='dim'),
        border_style='magenta',
        box=box.ROUNDED,
        padding=(1, 2),
    )


def build_hunt_memory_browser(browser):
    """Build a deterministic vertical snapshot for rendering tests."""
    return Group(
        build_hunt_memory_navigation(browser),
        Text(''),
        build_hunt_memory_preview(browser),
        Text('summary.log is system-owned and read-only.', style='dim'),
    )


def format_hunt_memory_browser(browser, width=120):
    output = StringIO()
    render_console = Console(
        file=output,
        width=width,
        force_terminal=False,
        color_system=None,
    )
    render_console.print(build_hunt_memory_browser(browser))
    return output.getvalue().rstrip()


def _run_memory_browser(console, browser):
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.key_binding.defaults import load_key_bindings
    from prompt_toolkit.key_binding.key_bindings import merge_key_bindings
    from prompt_toolkit.layout import Dimension, Layout
    from prompt_toolkit.layout.containers import (
        DynamicContainer,
        HSplit,
        VSplit,
        Window,
    )
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

    syncing_editor = False

    def editor_changed(buffer):
        if not syncing_editor:
            browser.update_draft(buffer.text)

    editor_buffer = Buffer(
        multiline=True,
        history=None,
        on_text_changed=editor_changed,
    )
    title_buffer = Buffer(multiline=False, history=None)
    keys = KeyBindings()
    browsing = Condition(lambda: browser.mode == 'browse')
    editing = Condition(lambda: browser.mode == 'edit')
    naming = Condition(lambda: browser.mode == 'title')
    confirming = Condition(lambda: browser.mode == 'confirm')

    navigation_control = FormattedTextControl(
        lambda: _render_ansi(
            build_hunt_memory_navigation(browser),
            width=46,
        ),
        focusable=True,
        show_cursor=False,
    )
    navigation_window = Window(
        content=navigation_control,
        wrap_lines=False,
        width=Dimension(min=32, preferred=46),
    )
    preview_control = FormattedTextControl(
        lambda: _render_ansi(
            build_hunt_memory_preview(browser),
            width=max(50, getattr(console, 'width', 100) - 47),
        ),
        focusable=True,
        show_cursor=False,
    )
    preview_window = Window(content=preview_control, wrap_lines=True)
    editor_control = BufferControl(buffer=editor_buffer)
    editor_window = Window(content=editor_control, wrap_lines=True)
    title_control = BufferControl(buffer=title_buffer)
    title_window = Window(content=title_control, height=1)

    editor_pane = HSplit([
        Window(
            FormattedTextControl(
                lambda: [
                    ('class:title', f' ◆ Editing {browser.edit_title or ""}'),
                    ('class:dirty', '  * unsaved' if browser.dirty else ''),
                ]
            ),
            height=1,
        ),
        editor_window,
    ])
    title_pane = HSplit([
        Window(
            FormattedTextControl(' New memory title'),
            height=1,
            style='bold',
        ),
        title_window,
        Window(
            FormattedTextControl(
                ' Letters, numbers, spaces, dots, underscores, or hyphens'
            ),
            height=1,
            style='dim',
        ),
    ])
    right_pane = DynamicContainer(
        lambda: (
            editor_pane
            if browser.mode in ('edit', 'confirm') and browser.edit_title
            else title_pane
            if browser.mode == 'title'
            else preview_window
        )
    )

    header = Window(
        FormattedTextControl(
            ' ↑/↓ move  Enter/e edit  n new  d delete  r refresh  '
            'Ctrl+S save  Esc back  q browse-close  Ctrl+Q close'
        ),
        height=1,
        style='dim',
    )
    footer = Window(
        FormattedTextControl(
            lambda: _footer_fragments(browser)
        ),
        height=2,
    )
    body = VSplit([
        navigation_window,
        Window(width=1, char='│', style='class:separator'),
        right_pane,
    ])
    layout = Layout(HSplit([header, body, footer]), focused_element=navigation_window)

    def sync_editor():
        nonlocal syncing_editor
        syncing_editor = True
        editor_buffer.set_document(
            Document(browser.draft, cursor_position=len(browser.draft)),
            bypass_readonly=True,
        )
        syncing_editor = False

    def focus_navigation(event):
        event.app.layout.focus(navigation_window)

    def focus_editor(event):
        sync_editor()
        event.app.layout.focus(editor_window)

    @keys.add('up', filter=browsing)
    def _up(_event):
        browser.move(-1)

    @keys.add('down', filter=browsing)
    def _down(_event):
        browser.move(1)

    @keys.add('pageup', filter=browsing)
    def _page_up(_event):
        browser.move(-MEMORY_VISIBLE_ITEMS)

    @keys.add('pagedown', filter=browsing)
    def _page_down(_event):
        browser.move(MEMORY_VISIBLE_ITEMS)

    @keys.add('home', filter=browsing)
    def _home(_event):
        browser.select_first()

    @keys.add('end', filter=browsing)
    def _end(_event):
        browser.select_last()

    @keys.add('enter', filter=browsing)
    @keys.add('e', filter=browsing)
    def _edit(event):
        if browser.begin_edit():
            focus_editor(event)

    @keys.add('n', filter=browsing)
    def _new(event):
        if browser.request_new():
            title_buffer.set_document(Document(''), bypass_readonly=True)
            event.app.layout.focus(title_window)

    @keys.add('enter', filter=naming)
    def _accept_title(event):
        if browser.begin_new(title_buffer.text):
            focus_editor(event)

    @keys.add('escape', filter=naming, eager=True)
    def _cancel_title(event):
        browser.cancel_title()
        focus_navigation(event)

    @keys.add('c-s', filter=editing)
    def _save(event):
        browser.update_draft(editor_buffer.text)
        if browser.save():
            focus_navigation(event)

    @keys.add('escape', filter=editing, eager=True)
    def _finish_edit(event):
        browser.update_draft(editor_buffer.text)
        if browser.request_finish_edit():
            focus_navigation(event)
        elif browser.mode == 'confirm':
            focus_navigation(event)

    @keys.add('d', filter=browsing)
    def _delete(event):
        if browser.request_delete():
            focus_navigation(event)

    @keys.add('r', filter=browsing)
    def _refresh(_event):
        browser.refresh()

    @keys.add('y', filter=confirming)
    def _confirm_yes(event):
        if browser.answer_confirmation(True):
            event.app.exit()
        elif browser.mode == 'edit':
            focus_editor(event)
        else:
            focus_navigation(event)

    @keys.add('n', filter=confirming)
    @keys.add('escape', filter=confirming, eager=True)
    def _confirm_no(event):
        browser.answer_confirmation(False)
        if browser.mode == 'edit':
            focus_editor(event)
        else:
            focus_navigation(event)

    @keys.add('q', filter=browsing)
    @keys.add('escape', filter=browsing, eager=True)
    def _quit_browse(event):
        if browser.request_quit():
            event.app.exit()

    @keys.add('c-q')
    @keys.add('c-c')
    def _quit_anywhere(event):
        if browser.mode == 'confirm':
            browser.answer_confirmation(False)
            focus_editor(event) if browser.mode == 'edit' else focus_navigation(event)
            return
        browser.update_draft(editor_buffer.text)
        if browser.request_quit():
            event.app.exit()
        elif browser.mode == 'confirm':
            focus_navigation(event)

    application = Application(
        layout=layout,
        key_bindings=merge_key_bindings([load_key_bindings(), keys]),
        full_screen=True,
        style=None,
    )
    application.run()


def _footer_fragments(browser):
    if browser.mode == 'confirm':
        message = browser.confirmation_message
        style = 'class:warning'
    else:
        message = browser.status or 'Ready.'
        style = 'class:status'
    return [
        (style, f' {message}\n'),
        ('class:readonly', ' summary.log is system-owned and read-only.'),
    ]


def _render_ansi(renderable, width):
    output = StringIO()
    render_console = Console(
        file=output,
        width=max(20, width),
        force_terminal=True,
    )
    render_console.print(renderable)
    from prompt_toolkit.formatted_text import ANSI
    return ANSI(output.getvalue())


def _title_error(title):
    if _is_summary_log(title):
        return 'summary.log is system-owned and read-only.'
    if not _MEMORY_TITLE.fullmatch(title):
        return (
            'Title must use 1-128 letters, numbers, spaces, dots, '
            'underscores, or hyphens.'
        )
    return ''


def _is_summary_log(title):
    return str(title or '').strip().casefold() == SUMMARY_LOG_TITLE


def _item_title(item):
    return str(item.get('title') or item.get('name') or '').strip()


def _updated(item):
    return str(item.get('updated') or item.get('created') or '—')


def _safe_multiline(value):
    return ''.join(
        character if character in '\n\t' or character.isprintable() else ' '
        for character in str(value or '')
    )
