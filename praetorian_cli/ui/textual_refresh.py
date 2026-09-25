import asyncio
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static


REFRESH_SPINNER_FRAMES = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')


@dataclass(frozen=True)
class RefreshResult:
    value: object = None
    error: Exception | None = None


class RefreshModal(ModalScreen[RefreshResult]):
    """Blocking visual feedback for an explicitly requested refresh."""

    CSS = """
    RefreshModal {
        align: center middle;
        background: #374151 75%;
    }
    #refresh-message {
        width: 40;
        height: 5;
        content-align: center middle;
        background: #111827;
        color: #f8fafc;
        border: heavy #a855f7;
        text-style: bold;
    }
    """

    def __init__(self, view_name, operation):
        super().__init__()
        self.view_name = str(view_name or 'VIEW').upper()
        self.operation = operation
        self._spinner_index = 0
        self._operation_task = None

    def compose(self) -> ComposeResult:
        yield Static(self._message(), id='refresh-message')

    def on_mount(self):
        self.set_interval(0.1, self._advance_spinner)
        self._operation_task = asyncio.create_task(self._run_operation())

    def on_unmount(self):
        task = self._operation_task
        if (
            task is not None
            and task is not asyncio.current_task()
            and not task.done()
        ):
            task.cancel()

    def _message(self):
        spinner = REFRESH_SPINNER_FRAMES[self._spinner_index]
        return f'REFRESHING {self.view_name}  {spinner}'

    def _advance_spinner(self):
        self._spinner_index = (
            self._spinner_index + 1
        ) % len(REFRESH_SPINNER_FRAMES)
        self.query_one('#refresh-message', Static).update(self._message())

    async def _run_operation(self):
        try:
            value = await self.operation()
            result = RefreshResult(value=value)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result = RefreshResult(error=exc)
        if self.is_current:
            self.dismiss(result)


def start_background_task(tasks, coroutine, on_error=None):
    """Start an owned task and always consume its terminal exception."""
    task = asyncio.create_task(coroutine)
    tasks.add(task)

    def finished(completed):
        tasks.discard(completed)
        if completed.cancelled():
            return
        error = completed.exception()
        if error is not None and on_error is not None:
            on_error(error)

    task.add_done_callback(finished)
    return task
