from io import StringIO

from rich.console import Console

from praetorian_cli.ui import hunt_memory
from praetorian_cli.ui.hunt_memory import (
    MEMORY_REFRESH_MAX_PAGES,
    HuntMemoryBrowser,
    browse_hunt_memory,
    format_hunt_memory_browser,
)


class FakeHunts:
    def __init__(self, items=None, contents=None):
        self.items = list(items or [])
        self.contents = dict(contents or {})
        self.calls = []
        self.next_offset = None

    def list_memory(self, hunt_id, pages=None):
        self.calls.append(('list', hunt_id, pages))
        return list(self.items), self.next_offset

    def get_memory(self, hunt_id, title):
        self.calls.append(('get', hunt_id, title))
        return self.contents.get(title, '')

    def save_memory(self, hunt_id, title, content):
        self.calls.append(('save', hunt_id, title, content))
        self.contents[title] = content

    def delete_memory(self, hunt_id, title):
        self.calls.append(('delete', hunt_id, title))
        self.items = [item for item in self.items if item['title'] != title]


def _browser():
    hunts = FakeHunts(
        items=[
            {'title': 'alpha.md', 'updated': '2026-09-01T00:00:00Z'},
            {'title': 'beta.md', 'updated': '2026-09-02T00:00:00Z'},
        ],
        contents={
            'alpha.md': 'first line\nsecond line',
            'beta.md': 'beta context',
        },
    )
    browser = HuntMemoryBrowser(hunts, 'hunt-1', hunts.items)
    browser.load_current()
    return browser, hunts


def test_memory_browser_navigates_without_hiding_list_and_renders_multiline():
    browser, _ = _browser()

    browser.move(1)
    rendered = format_hunt_memory_browser(browser, width=100)

    assert browser.current_title == 'beta.md'
    assert 'alpha.md' in rendered
    assert 'beta.md' in rendered
    assert 'beta context' in rendered
    assert 'summary.log is system-owned and read-only' in rendered


def test_memory_browser_edits_multiline_and_confirms_dirty_discard():
    browser, hunts = _browser()

    assert browser.begin_edit() is True
    browser.update_draft('first line\nreplacement\nthird line')
    assert browser.dirty is True
    assert browser.request_finish_edit() is False
    assert browser.mode == 'confirm'

    browser.answer_confirmation(False)
    assert browser.mode == 'edit'
    assert browser.dirty is True
    assert browser.save() is True

    assert ('save', 'hunt-1', 'alpha.md', 'first line\nreplacement\nthird line') in hunts.calls
    assert browser.mode == 'browse'
    assert browser.dirty is False


def test_memory_browser_requires_confirmation_before_quitting_dirty_editor():
    browser, hunts = _browser()
    browser.begin_edit()
    browser.update_draft('unsaved replacement')

    assert browser.request_quit() is False
    assert browser.mode == 'confirm'
    assert 'Discard unsaved changes' in browser.confirmation_message
    assert browser.answer_confirmation(True) is True
    assert not any(call[0] == 'save' for call in hunts.calls)


def test_memory_browser_creates_and_deletes_only_through_hunt_api():
    browser, hunts = _browser()

    browser.request_new()
    assert browser.begin_new('summary.log') is False
    assert 'system-owned and read-only' in browser.status
    assert browser.begin_new('operator notes.md') is True
    browser.update_draft('line one\nline two')
    assert browser.save() is True
    assert browser.current_title == 'operator notes.md'

    assert browser.request_delete() is True
    assert browser.answer_confirmation(True) is False

    assert ('save', 'hunt-1', 'operator notes.md', 'line one\nline two') in hunts.calls
    assert ('delete', 'hunt-1', 'operator notes.md') in hunts.calls
    assert browser.current_title in {'alpha.md', 'beta.md'}


def test_memory_browser_refresh_is_bounded_and_preserves_selection():
    browser, hunts = _browser()
    browser.move(1)
    hunts.items = [
        {'title': 'beta.md', 'updated': 'new'},
        {'title': 'gamma.md', 'updated': 'new'},
    ]
    hunts.contents['gamma.md'] = 'gamma context'
    hunts.next_offset = {'key': 'more'}

    assert browser.refresh() is True

    assert ('list', 'hunt-1', MEMORY_REFRESH_MAX_PAGES) in hunts.calls
    assert browser.current_title == 'beta.md'
    assert browser.more_available is True
    assert 'additional items not loaded' in browser.status


def test_memory_browser_filters_system_log_defensively():
    hunts = FakeHunts(contents={'notes.md': 'editable'})
    browser = HuntMemoryBrowser(
        hunts,
        'hunt-1',
        [
            {'title': 'SUMMARY.LOG'},
            {'title': 'notes.md'},
        ],
    )

    assert [item['title'] for item in browser.items] == ['notes.md']


def test_non_tty_memory_browser_keeps_deterministic_static_output(monkeypatch):
    hunts = FakeHunts(
        items=[{'title': 'alpha.md', 'updated': 'today'}],
        contents={'alpha.md': 'content'},
    )
    output = StringIO()
    monkeypatch.setattr(
        hunt_memory,
        'supports_fullscreen_memory_browser',
        lambda: False,
    )

    opened = browse_hunt_memory(
        Console(file=output, force_terminal=False, color_system=None),
        hunts,
        'hunt-1',
    )

    assert opened is False
    assert hunts.calls == [('list', 'hunt-1', None)]
    assert 'alpha.md' in output.getvalue()


def test_fullscreen_editor_saves_multiline_input_without_a_prompt_history():
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    browser, hunts = _browser()
    with create_pipe_input() as input_pipe:
        # Enter starts editing, Enter inserts a newline, Ctrl+S saves, q closes.
        input_pipe.send_text('\r\nthird line\x13q')
        with create_app_session(input=input_pipe, output=DummyOutput()):
            hunt_memory._run_memory_browser(Console(), browser)

    assert ('save', 'hunt-1', 'alpha.md', 'first line\nsecond line\nthird line') in hunts.calls


def test_tty_memory_browser_initial_load_is_bounded(monkeypatch):
    hunts = FakeHunts(
        items=[{'title': 'alpha.md'}],
        contents={'alpha.md': 'content'},
    )
    opened = []
    monkeypatch.setattr(
        hunt_memory,
        'supports_fullscreen_memory_browser',
        lambda: True,
    )
    monkeypatch.setattr(
        hunt_memory,
        '_run_memory_browser',
        lambda _console, browser: opened.append(browser.current_title),
    )

    assert browse_hunt_memory(Console(), hunts, 'hunt-1') is True

    assert hunts.calls[:2] == [
        ('list', 'hunt-1', MEMORY_REFRESH_MAX_PAGES),
        ('get', 'hunt-1', 'alpha.md'),
    ]
    assert opened == ['alpha.md']
