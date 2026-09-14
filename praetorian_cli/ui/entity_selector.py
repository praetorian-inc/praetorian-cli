import sys

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


MAX_VISIBLE_ENTITIES = 25


def select_entity_keys(
    console,
    entities,
    title='Select targets',
    search_entities=None,
    next_offset=None,
    multiple=True,
):
    """Select entity keys with a fullscreen UI when a terminal is available."""
    if _supports_fullscreen_selector():
        return _run_interactive_selector(
            console,
            entities,
            title,
            search_entities,
            next_offset,
            multiple,
        )
    return _select_entity_keys_with_prompts(
        console,
        entities,
        title,
        search_entities,
        next_offset,
        multiple,
    )


class EntitySelector:
    """State for keyboard navigation, server paging, and search."""

    def __init__(
        self,
        entities,
        search_entities=None,
        next_offset=None,
        multiple=True,
    ):
        self.search_entities = search_entities
        self.multiple = multiple
        self.pages = [(_unique_entities(entities), next_offset)]
        self.page_index = 0
        self.cursor = 0
        self.query = ''
        self.applied_query = ''
        self.search_mode = False
        self.server_filtered = search_entities is not None
        self.selected_keys = []
        self.status = ''

    @property
    def rows(self):
        entities, _ = self.pages[self.page_index]
        if self.search_mode:
            return filter_entities(entities, self.query)
        if self.server_filtered:
            return entities
        return filter_entities(entities, self.applied_query)

    @property
    def visible_start(self):
        return (self.cursor // MAX_VISIBLE_ENTITIES) * MAX_VISIBLE_ENTITIES

    @property
    def visible_rows(self):
        start = self.visible_start
        return self.rows[start:start + MAX_VISIBLE_ENTITIES]

    @property
    def current(self):
        rows = self.rows
        return rows[self.cursor] if 0 <= self.cursor < len(rows) else None

    def move(self, delta):
        rows = self.rows
        if not rows:
            return
        next_cursor = self.cursor + delta
        if 0 <= next_cursor < len(rows):
            self.cursor = next_cursor
            return
        if delta > 0 and not self.search_mode and self._next_server_page():
            return
        if delta < 0 and not self.search_mode and self._previous_server_page():
            return
        self.cursor = min(max(next_cursor, 0), len(rows) - 1)

    def next_chunk(self):
        rows = self.rows
        next_cursor = self.visible_start + MAX_VISIBLE_ENTITIES
        if next_cursor < len(rows):
            self.cursor = next_cursor
            return
        if not self.search_mode and self._next_server_page():
            return
        self.status = 'No additional results.'

    def previous_chunk(self):
        if self.visible_start > 0:
            self.cursor = max(0, self.visible_start - MAX_VISIBLE_ENTITIES)
            return
        if not self.search_mode and self._previous_server_page():
            return
        self.status = 'Already at the first results.'

    def toggle_current(self):
        current = self.current
        if current is None:
            return
        key = _entity_key(current)
        if key in self.selected_keys:
            self.selected_keys.remove(key)
        else:
            self.selected_keys.append(key)
        self.status = f'{len(self.selected_keys)} selected'

    def confirmed_keys(self):
        if self.multiple:
            if not self.selected_keys:
                self.status = 'Select at least one target with Space.'
                return None
            return list(self.selected_keys)
        current = self.current
        if current is None:
            self.status = 'No target selected.'
            return None
        return [_entity_key(current)]

    def begin_search(self):
        self.search_mode = True
        self.query = self.applied_query
        self.cursor = 0
        self.status = 'Type a query, then press Enter to search the server.'

    def append_search(self, value):
        self.query += value
        self.cursor = 0

    def backspace_search(self):
        self.query = self.query[:-1]
        self.cursor = 0

    def clear_search(self):
        self.query = ''
        self.cursor = 0

    def cancel_search(self):
        self.query = self.applied_query
        self.search_mode = False
        self.cursor = 0
        self.status = ''

    def apply_search(self):
        if self.search_entities is None:
            self.applied_query = self.query
            self.search_mode = False
            self.cursor = 0
            return
        try:
            first_page = _load_entities(
                self.search_entities,
                self.query,
                None,
            )
        except Exception as exc:
            self.status = f'Search failed: {exc}'
            return
        self.pages = [first_page]
        self.page_index = 0
        self.cursor = 0
        self.applied_query = self.query
        self.search_mode = False
        self.server_filtered = True
        self.status = f'{len(self.rows)} results on this server page'

    def _next_server_page(self):
        if self.page_index + 1 < len(self.pages):
            self.page_index += 1
            self.cursor = 0
            self.status = ''
            return True
        _, next_offset = self.pages[self.page_index]
        if self.search_entities is None or next_offset is None:
            return False
        try:
            next_page = _load_entities(
                self.search_entities,
                self.applied_query,
                next_offset,
            )
        except Exception as exc:
            self.status = f'Unable to load next page: {exc}'
            return False
        self.pages.append(next_page)
        self.page_index += 1
        self.cursor = 0
        self.server_filtered = True
        self.status = ''
        return True

    def _previous_server_page(self):
        if self.page_index == 0:
            return False
        self.page_index -= 1
        self.cursor = max(0, len(self.rows) - 1)
        self.status = ''
        return True


def _supports_fullscreen_selector():
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def _run_interactive_selector(
    console,
    entities,
    title,
    search_entities,
    next_offset,
    multiple,
):
    from io import StringIO

    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    selector = EntitySelector(
        entities,
        search_entities=search_entities,
        next_offset=next_offset,
        multiple=multiple,
    )
    if not selector.rows:
        console.print('  No selectable targets found.')
        return []

    key_bindings = KeyBindings()

    @key_bindings.add('up')
    def _move_up(event):
        selector.move(-1)

    @key_bindings.add('down')
    def _move_down(event):
        selector.move(1)

    @key_bindings.add('pageup')
    @key_bindings.add('left')
    def _previous_page(event):
        selector.previous_chunk()

    @key_bindings.add('pagedown')
    @key_bindings.add('right')
    def _next_page(event):
        selector.next_chunk()

    @key_bindings.add('home')
    def _first_row(event):
        selector.cursor = 0

    @key_bindings.add('end')
    def _last_row(event):
        selector.cursor = max(0, len(selector.rows) - 1)

    @key_bindings.add(' ')
    def _space(event):
        if selector.search_mode:
            selector.append_search(' ')
        else:
            selector.toggle_current()

    @key_bindings.add('/')
    @key_bindings.add('c-f')
    def _begin_search(event):
        if selector.search_mode:
            selector.append_search('/')
        else:
            selector.begin_search()

    @key_bindings.add('backspace')
    def _backspace(event):
        if selector.search_mode:
            selector.backspace_search()

    @key_bindings.add('c-u')
    def _clear_search(event):
        if selector.search_mode:
            selector.clear_search()

    @key_bindings.add('enter')
    def _confirm(event):
        if selector.search_mode:
            selector.apply_search()
            return
        selected = selector.confirmed_keys()
        if selected is not None:
            event.app.exit(result=selected)

    @key_bindings.add('q')
    def _quit(event):
        if selector.search_mode:
            selector.append_search('q')
        else:
            event.app.exit(result=[])

    @key_bindings.add('escape')
    def _escape(event):
        if selector.search_mode:
            selector.cancel_search()
        else:
            event.app.exit(result=[])

    @key_bindings.add('c-c')
    def _cancel(event):
        event.app.exit(result=[])

    @key_bindings.add(Keys.Any)
    def _type_search(event):
        if selector.search_mode and event.data.isprintable():
            selector.append_search(event.data)

    def display():
        output = StringIO()
        render_console = Console(
            file=output,
            force_terminal=True,
            width=max(80, getattr(console, 'width', 80)),
        )
        render_console.print(
            '↑/↓ move  SPACE toggle  ENTER confirm  / search  '
            '←/→ page  ESC cancel',
            style='dim',
        )
        search = Text('Search  ', style='bold cyan')
        search.append(selector.query or '—', style='white')
        if selector.search_mode:
            search.append('█', style='cyan')
            search.append('  ENTER searches server', style='dim')
        render_console.print(search)
        current_key = _entity_key(selector.current or {})
        render_console.print(_selection_table(
            selector.visible_rows,
            title,
            set(selector.selected_keys),
            cursor_key=current_key,
            row_number_start=selector.visible_start,
        ))
        render_console.print(
            f'Server page {selector.page_index + 1} · '
            f'{len(selector.selected_keys)} selected',
            style='dim',
        )
        if selector.status:
            render_console.print(selector.status, style='yellow')
        return ANSI(output.getvalue())

    application = Application(
        layout=Layout(Window(content=FormattedTextControl(display))),
        key_bindings=key_bindings,
        full_screen=True,
    )
    return application.run() or []


def _select_entity_keys_with_prompts(
    console,
    entities,
    title='Select targets',
    search_entities=None,
    next_offset=None,
    multiple=True,
):
    """Interactively search and multi-select entity keys without typing them."""
    entities = _unique_entities(entities)
    if not entities:
        console.print('  No selectable targets found.')
        return []

    query = ''
    server_filtered = False
    selected_keys = []
    pages = [(entities, next_offset)]
    page_index = 0
    display_start = 0

    while True:
        entities, current_next_offset = pages[page_index]
        matches = entities if server_filtered else filter_entities(entities, query)
        visible = matches[
            display_start:display_start + MAX_VISIBLE_ENTITIES
        ]
        console.print(_selection_table(visible, title, set(selected_keys)))

        visible_end = min(display_start + len(visible), len(matches))
        if len(matches) > MAX_VISIBLE_ENTITIES:
            console.print(
                f'  Showing {display_start + 1}-{visible_end} of '
                f'{len(matches)} results on this server page.',
                style='dim',
            )

        has_previous = display_start > 0 or page_index > 0
        has_next = (
            display_start + MAX_VISIBLE_ENTITIES < len(matches)
            or page_index + 1 < len(pages)
            or current_next_offset is not None
        )
        actions = '/search terms'
        if has_previous:
            actions += ', prev'
        if has_next:
            actions += ', next'
        prompt = (
            f'  Toggle row numbers, {actions}, done, or q'
            if multiple
            else f'  Select one row number, {actions}, or q'
        )
        response = Prompt.ask(prompt).strip()
        if response.lower() in {'q', 'quit'}:
            return []
        if response.lower() in {'done', 'd'}:
            if multiple and selected_keys:
                return selected_keys
            if multiple:
                console.print('  Select at least one target.', style='red')
                continue
            console.print('  Choose one row number.', style='red')
            continue
        if response.lower().startswith('/search'):
            query = response[7:].strip()
            display_start = 0
            page_index = 0
            if search_entities is not None:
                first_page = _load_entities(search_entities, query, None)
                pages = [first_page]
                server_filtered = True
            else:
                server_filtered = False
            continue
        if response.lower() in {'next', 'n'}:
            if display_start + MAX_VISIBLE_ENTITIES < len(matches):
                display_start += MAX_VISIBLE_ENTITIES
                continue
            if page_index + 1 < len(pages):
                page_index += 1
                display_start = 0
                continue
            if search_entities is not None and current_next_offset is not None:
                next_page = _load_entities(
                    search_entities,
                    query,
                    current_next_offset,
                )
                pages.append(next_page)
                page_index += 1
                display_start = 0
                server_filtered = True
                continue
            console.print('  No additional results.', style='dim')
            continue
        if response.lower() in {'prev', 'previous', 'p'}:
            if display_start > 0:
                display_start = max(0, display_start - MAX_VISIBLE_ENTITIES)
                continue
            if page_index > 0:
                page_index -= 1
                previous_entities, _ = pages[page_index]
                previous_matches = (
                    previous_entities
                    if server_filtered
                    else filter_entities(previous_entities, query)
                )
                display_start = max(
                    0,
                    ((len(previous_matches) - 1) // MAX_VISIBLE_ENTITIES)
                    * MAX_VISIBLE_ENTITIES,
                )
                continue
            console.print('  Already at the first results.', style='dim')
            continue
        try:
            indices = parse_selection(response, len(visible))
        except ValueError as exc:
            console.print(f'  {exc}', style='red')
            continue
        if not multiple:
            if len(indices) != 1:
                console.print('  Choose exactly one row.', style='red')
                continue
            return [_entity_key(visible[indices[0]])]
        for index in indices:
            key = _entity_key(visible[index])
            if key in selected_keys:
                selected_keys.remove(key)
            else:
                selected_keys.append(key)


def _load_entities(loader, query, offset):
    result = loader(query, offset)
    if isinstance(result, tuple) and len(result) == 2:
        entities, next_offset = result
    else:
        entities, next_offset = result, None
    return _unique_entities(entities), next_offset


def filter_entities(entities, query):
    terms = [term.lower() for term in query.split() if term]
    if not terms:
        return list(entities)
    return [
        entity for entity in entities
        if all(term in _search_text(entity) for term in terms)
    ]


def parse_selection(value, item_count):
    if not value:
        raise ValueError('select at least one target')
    selected = []
    for token in value.split(','):
        token = token.strip()
        if not token.isdigit():
            raise ValueError('selections must be comma-separated row numbers')
        index = int(token) - 1
        if index < 0 or index >= item_count:
            raise ValueError(f'selection {token} is outside the displayed rows')
        if index not in selected:
            selected.append(index)
    return selected


def _selection_table(
    entities,
    title,
    selected_keys,
    cursor_key=None,
    row_number_start=0,
):
    table = Table(
        title=Text(title, style='bold cyan'),
        box=box.ROUNDED,
        border_style='cyan',
        header_style='bold',
        expand=True,
    )
    table.add_column('', width=3)
    table.add_column('#', width=4, justify='right')
    table.add_column('TARGET', min_width=20, ratio=2)
    table.add_column('IDENTIFIER', min_width=14, ratio=2)
    table.add_column('CANONICAL KEY', min_width=22, ratio=3)
    table.add_column('TYPE', width=12)
    table.add_column('STATUS', width=9)
    for index, entity in enumerate(entities, start=1):
        key = _entity_key(entity)
        marker = Text()
        marker.append('▶' if key == cursor_key else ' ', style='bold cyan')
        marker.append('✓' if key in selected_keys else ' ', style='bold green')
        table.add_row(
            marker,
            str(row_number_start + index),
            Text(_display(_entity_label(entity))),
            Text(_display(_entity_identifier(entity))),
            Text(_display(key), style='dim'),
            Text(_display(entity.get('class') or entity.get('type') or '—')),
            Text(_display(entity.get('status') or '—')),
        )
    if not entities:
        table.add_row(
            '', '', Text('No matching targets.', style='dim'), '', '', '', ''
        )
    return table


def _unique_entities(entities):
    unique = {}
    for entity in entities or []:
        key = _entity_key(entity)
        if key:
            unique.setdefault(key, entity)
    return list(unique.values())


def _entity_key(entity):
    return str(entity.get('key') or '') if isinstance(entity, dict) else ''


def _entity_label(entity):
    return str(
        entity.get('title')
        or entity.get('name')
        or entity.get('dns')
        or entity.get('primary_url')
        or entity.get('identifier')
        or _entity_key(entity)
    )


def _entity_identifier(entity):
    values = [
        entity.get('dns'),
        entity.get('identifier'),
        entity.get('primary_url'),
    ]
    label = _entity_label(entity)
    return str(next((value for value in values if value and value != label), '—'))


def _display(value):
    return ''.join(
        character if character.isprintable() else ' '
        for character in str(value or '')
    )


def _search_text(entity):
    return ' '.join(
        str(entity.get(field) or '').lower()
        for field in (
            'key',
            'title',
            'name',
            'dns',
            'identifier',
            'primary_url',
            'class',
            'type',
        )
    )
