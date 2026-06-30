"""Hannibal Hunt TUI — Claude Code-style interactive hunt interface."""
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, RichLog
from textual.reactive import reactive
from textual import on, work

from praetorian_cli.sdk.chariot import Chariot


HUNT_LOGO = r"""[bold red]
  ╦ ╦╔═╗╔╗╔╔╗╔╦╗╔╗ ╔═╗╦
  ╠═╣╠═╣║║║║║║║╠╩╗╠═╣║
  ╩ ╩╩ ╩╝╚╝╝╚╝╩╚═╝╩ ╩╩═╝[/bold red]"""

STATUS_STYLE = {
    'active': '[bold green]● active[/bold green]',
    'paused': '[bold yellow]● paused[/bold yellow]',
    'completed': '[bold cyan]● completed[/bold cyan]',
    'stopped': '[bold red]● stopped[/bold red]',
    'expired': '[bold magenta]● expired[/bold magenta]',
    'errored': '[bold red]● errored[/bold red]',
}


class HuntApp(App):
    """Interactive Hannibal hunt management TUI."""

    TITLE = "Hannibal"

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #context-bar {
        height: 3;
        background: $primary-background;
        color: $text;
        padding: 0 2;
        border-bottom: solid $primary;
    }

    #activity-log {
        height: 1fr;
        margin: 0 1;
        scrollbar-size: 1 1;
    }

    #input-container {
        height: 3;
        margin: 0 1 0 1;
        border-top: solid $primary;
    }

    #hunt-input {
        width: 1fr;
    }

    #status-bar {
        height: 1;
        background: $primary-background;
        color: $text-muted;
        padding: 0 2;
        border-top: solid $primary;
    }

    .activity-info {
        color: $text-muted;
    }

    .activity-finding {
        color: $warning;
    }

    .activity-error {
        color: $error;
    }

    .activity-action {
        color: $accent;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+p", "pause_resume", "Pause/Resume"),
        ("ctrl+s", "stop_hunt", "Stop Hunt"),
    ]

    hunt_uuid: reactive[Optional[str]] = reactive(None)
    hunt_status: reactive[str] = reactive("")

    def __init__(self, sdk: Chariot, hunt_uuid: str = None, start_prompt: str = None,
                 start_duration: str = '24h', start_scope: list = None):
        super().__init__()
        self.sdk = sdk
        self._initial_uuid = hunt_uuid
        self._start_prompt = start_prompt
        self._start_duration = start_duration
        self._start_scope = start_scope or []
        self._prev_iteration_count = -1
        self._prev_findings_count = -1
        self._poll_interval = 5

        try:
            self.user_email, self.username = self.sdk.get_current_user()
        except Exception:
            self.user_email = 'unknown'
            self.username = 'unknown'

        self._account = getattr(self.sdk.keychain, '_account', None) or ''

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="context-bar")
        yield RichLog(id="activity-log", highlight=True, markup=True, wrap=True)
        with Container(id="input-container"):
            yield Input(placeholder="Type a command... (/help for commands)", id="hunt-input")
        yield Static(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._update_context_bar()
        log = self.query_one("#activity-log", RichLog)
        log.write(HUNT_LOGO)
        log.write("")

        if self._initial_uuid:
            self.hunt_uuid = self._initial_uuid
            log.write(f"[dim]Connecting to hunt {self._initial_uuid}...[/dim]")
            self._poll_hunt()
        elif self._start_prompt:
            log.write("[dim]Launching new hunt...[/dim]")
            self._launch_hunt()
        else:
            log.write("[bold]Welcome to Hannibal[/bold]")
            log.write("")
            log.write("Start a hunt or connect to an existing one:")
            log.write("  [cyan]/start[/cyan] <prompt>  — launch a new hunt")
            log.write("  [cyan]/connect[/cyan] <uuid>  — connect to a running hunt")
            log.write("  [cyan]/list[/cyan]            — show all hunts")
            log.write("  [cyan]/help[/cyan]            — all commands")
            log.write("")

        self.query_one("#hunt-input").focus()
        self._start_polling()

    def _update_context_bar(self) -> None:
        bar = self.query_one("#context-bar", Static)
        parts = [f"[bold]Hannibal[/bold]"]
        if self.user_email and self.user_email != 'unknown':
            parts.append(f"[dim]user:[/dim] {self.user_email}")
        if self._account:
            parts.append(f"[dim]account:[/dim] {self._account}")
        if self.hunt_uuid:
            parts.append(f"[dim]hunt:[/dim] {self.hunt_uuid[:8]}...")
        if self.hunt_status:
            parts.append(STATUS_STYLE.get(self.hunt_status, self.hunt_status))
        bar.update("  ".join(parts))

    def _update_status_bar(self, hunt_data: dict = None) -> None:
        bar = self.query_one("#status-bar", Static)
        if not hunt_data:
            bar.update("[dim]No active hunt · /start to begin · /help for commands[/dim]")
            return
        iterations = hunt_data.get('iterationCount', 0)
        findings = hunt_data.get('findingsCount', 0)
        expires = hunt_data.get('expiresAt', '')
        remaining = ''
        if expires:
            try:
                exp = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                delta = exp - datetime.now(timezone.utc)
                hours = int(delta.total_seconds() // 3600)
                mins = int((delta.total_seconds() % 3600) // 60)
                if delta.total_seconds() > 0:
                    remaining = f"{hours}h{mins}m remaining"
                else:
                    remaining = "expired"
            except Exception:
                remaining = ''
        parts = [
            f"iterations: {iterations}",
            f"findings: {findings}",
        ]
        if remaining:
            parts.append(remaining)
        parts.append("/help for commands")
        bar.update("[dim]" + " · ".join(parts) + "[/dim]")

    @work(thread=True)
    def _launch_hunt(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        try:
            from datetime import timedelta
            hours = _parse_duration_int(self._start_duration)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
            body = {'prompt': self._start_prompt, 'expiresAt': expires_at}
            if self._start_scope:
                body['scope'] = self._start_scope

            result = self.sdk.post('hunt', body)
            self.hunt_uuid = result.get('uuid', '')
            self.hunt_status = result.get('status', 'active')
            self._update_context_bar()

            log.write(f"[bold green]Hunt launched![/bold green]")
            log.write(f"  [dim]UUID:[/dim]    {self.hunt_uuid}")
            log.write(f"  [dim]Mandate:[/dim] {self._start_prompt}")
            log.write(f"  [dim]Expires:[/dim] {expires_at}")
            log.write("")
            self._update_status_bar(result)
        except Exception as e:
            log.write(f"[bold red]Failed to launch hunt:[/bold red] {e}")

    @work(thread=True)
    def _poll_hunt(self) -> None:
        if not self.hunt_uuid:
            return
        try:
            resp = self.sdk.my({'key': f'#hunt#{self.hunt_uuid}'})
            hunts = _extract_hunts(resp)
            if not hunts:
                log = self.query_one("#activity-log", RichLog)
                log.write(f"[red]Hunt {self.hunt_uuid} not found.[/red]")
                return
            h = hunts[0]
            self.hunt_status = h.get('status', '')
            self._update_context_bar()
            self._update_status_bar(h)
            self._emit_changes(h)
        except Exception:
            pass

    def _emit_changes(self, h: dict) -> None:
        log = self.query_one("#activity-log", RichLog)
        iterations = h.get('iterationCount', 0)
        findings = h.get('findingsCount', 0)

        if iterations != self._prev_iteration_count and self._prev_iteration_count >= 0:
            ts = time.strftime('%H:%M:%S')
            log.write(f"[dim]{ts}[/dim]  [cyan]Iteration {iterations} started[/cyan]")

        if findings != self._prev_findings_count and self._prev_findings_count >= 0:
            ts = time.strftime('%H:%M:%S')
            delta = findings - self._prev_findings_count
            log.write(f"[dim]{ts}[/dim]  [bold yellow]⚠ {delta} new finding(s)[/bold yellow] (total: {findings})")

        status = h.get('status', '')
        if status in ('completed', 'stopped', 'expired', 'errored') and self.hunt_status != status:
            ts = time.strftime('%H:%M:%S')
            log.write(f"[dim]{ts}[/dim]  {STATUS_STYLE.get(status, status)}")
            last_error = h.get('lastError', '')
            if last_error:
                log.write(f"  [red]{last_error}[/red]")

        self._prev_iteration_count = iterations
        self._prev_findings_count = findings

    def _start_polling(self) -> None:
        self.set_interval(self._poll_interval, self._poll_hunt)

    @on(Input.Submitted, "#hunt-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        self._handle_command(text)

    def _handle_command(self, text: str) -> None:
        log = self.query_one("#activity-log", RichLog)

        if text.startswith('/'):
            parts = text[1:].split(None, 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ''

            if cmd == 'help':
                self._show_help()
            elif cmd == 'start':
                if not args:
                    log.write("[red]Usage: /start <prompt>[/red]")
                    return
                self._start_prompt = args
                self._launch_hunt()
            elif cmd == 'connect':
                if not args:
                    log.write("[red]Usage: /connect <uuid>[/red]")
                    return
                self.hunt_uuid = args.strip()
                self._prev_iteration_count = -1
                self._prev_findings_count = -1
                log.write(f"[dim]Connecting to {self.hunt_uuid}...[/dim]")
                self._poll_hunt()
            elif cmd == 'list':
                self._list_hunts()
            elif cmd == 'pause':
                self._set_status('paused')
            elif cmd == 'resume':
                self._set_status('active')
            elif cmd == 'stop':
                self._set_status('stopped')
            elif cmd == 'status':
                self._poll_hunt()
            elif cmd == 'cost':
                self._show_cost()
            elif cmd == 'show':
                self._show_details()
            elif cmd in ('ask', 'marcus'):
                if not args:
                    log.write("[red]Usage: /ask <question>[/red]")
                    return
                self._ask_marcus(args)
            elif cmd == 'quit' or cmd == 'exit':
                self.exit()
            elif cmd == 'clear':
                log.clear()
            else:
                log.write(f"[red]Unknown command: /{cmd}[/red] — type /help for commands")
        else:
            log.write(f"[dim]Type /help for commands. Prefix commands with /[/dim]")

    def _show_help(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        log.write("")
        log.write("[bold]Hunt Commands[/bold]")
        log.write("  [cyan]/start[/cyan]   <prompt>  Launch a new hunt")
        log.write("  [cyan]/connect[/cyan] <uuid>   Connect to an existing hunt")
        log.write("  [cyan]/list[/cyan]             List all hunts")
        log.write("  [cyan]/show[/cyan]             Show current hunt details")
        log.write("  [cyan]/status[/cyan]           Refresh hunt status")
        log.write("  [cyan]/cost[/cyan]             Show AI cost breakdown")
        log.write("")
        log.write("[bold]Hunt Control[/bold]")
        log.write("  [cyan]/pause[/cyan]            Pause the current hunt")
        log.write("  [cyan]/resume[/cyan]           Resume a paused hunt")
        log.write("  [cyan]/stop[/cyan]             Stop the hunt permanently")
        log.write("")
        log.write("[bold]General[/bold]")
        log.write("[bold]Marcus AI[/bold]")
        log.write("  [cyan]/ask[/cyan]    <question>  Ask Marcus a question")
        log.write("  [cyan]/marcus[/cyan] <question>  Same as /ask")
        log.write("")
        log.write("[bold]General[/bold]")
        log.write("  [cyan]/clear[/cyan]            Clear the activity log")
        log.write("  [cyan]/quit[/cyan]             Exit (hunt continues running)")
        log.write("")
        log.write("[bold]Keyboard Shortcuts[/bold]")
        log.write("  [cyan]Ctrl+P[/cyan]  Pause/Resume")
        log.write("  [cyan]Ctrl+S[/cyan]  Stop hunt")
        log.write("  [cyan]Ctrl+C[/cyan]  Quit")
        log.write("")

    @work(thread=True)
    def _list_hunts(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        try:
            resp = self.sdk.my({'key': '#hunt'})
            hunts = _extract_hunts(resp)
            if not hunts:
                log.write("[dim]No hunts found.[/dim]")
                return
            log.write(f"[bold]{len(hunts)} hunt(s)[/bold]")
            for h in hunts:
                uuid = h.get('uuid', '?')
                status = h.get('status', '?')
                style = STATUS_STYLE.get(status, status)
                prompt = (h.get('prompt', '') or '')[:50]
                iters = h.get('iterationCount', 0)
                finds = h.get('findingsCount', 0)
                log.write(f"  {uuid[:12]}...  {style}  i={iters} f={finds}  {prompt}")
        except Exception as e:
            log.write(f"[red]Error listing hunts: {e}[/red]")

    @work(thread=True)
    def _set_status(self, new_status: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        if not self.hunt_uuid:
            log.write("[red]No hunt connected. Use /connect <uuid> or /start <prompt>[/red]")
            return
        try:
            result = self.sdk.put(f'hunt/{self.hunt_uuid}', {'status': new_status})
            self.hunt_status = result.get('status', new_status)
            self._update_context_bar()
            ts = time.strftime('%H:%M:%S')
            log.write(f"[dim]{ts}[/dim]  Hunt {STATUS_STYLE.get(new_status, new_status)}")
            self._update_status_bar(result)
        except Exception as e:
            log.write(f"[red]Failed to {new_status} hunt: {e}[/red]")

    @work(thread=True)
    def _show_cost(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        if not self.hunt_uuid:
            log.write("[red]No hunt connected.[/red]")
            return
        try:
            result = self.sdk.get(f'hunt/{self.hunt_uuid}/cost')
            total = result.get('total', {})
            cost = total.get('cost', 0)
            calls = total.get('call_count', 0)
            input_tok = total.get('input_tokens', 0)
            output_tok = total.get('output_tokens', 0)
            log.write("")
            log.write(f"[bold]AI Cost[/bold]  ${cost:.4f}")
            log.write(f"  API calls:     {calls}")
            log.write(f"  Input tokens:  {input_tok:,}")
            log.write(f"  Output tokens: {output_tok:,}")

            by_model = result.get('by_model') or []
            if by_model:
                log.write(f"  [dim]By model:[/dim]")
                for m in by_model:
                    log.write(f"    {m.get('model', '?')}: ${m.get('cost', 0):.4f} ({m.get('call_count', 0)} calls)")
            log.write("")
        except Exception as e:
            log.write(f"[red]Failed to get cost: {e}[/red]")

    @work(thread=True)
    def _show_details(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        if not self.hunt_uuid:
            log.write("[red]No hunt connected.[/red]")
            return
        try:
            resp = self.sdk.my({'key': f'#hunt#{self.hunt_uuid}'})
            hunts = _extract_hunts(resp)
            if not hunts:
                log.write(f"[red]Hunt {self.hunt_uuid} not found.[/red]")
                return
            h = hunts[0]
            log.write("")
            log.write(f"[bold]Hunt Details[/bold]")
            log.write(f"  UUID:        {h.get('uuid', '?')}")
            log.write(f"  Status:      {STATUS_STYLE.get(h.get('status', ''), '?')}")
            log.write(f"  Created:     {h.get('created', '?')}")
            log.write(f"  Created By:  {h.get('createdBy', '?')}")
            log.write(f"  Expires:     {h.get('expiresAt', '?')}")
            log.write(f"  Agent:       {h.get('agent', 'hannibal')}")
            log.write(f"  Iterations:  {h.get('iterationCount', 0)}")
            log.write(f"  Findings:    {h.get('findingsCount', 0)}")
            prompt = h.get('prompt', '')
            if prompt:
                log.write(f"  Mandate:     {prompt}")
            scope = h.get('scope', [])
            if scope:
                log.write(f"  Scope:       {', '.join(scope)}")
            finish = h.get('finishCriteria', '')
            if finish:
                log.write(f"  Finish:      {finish}")
            last_error = h.get('lastError', '')
            if last_error:
                log.write(f"  Last Error:  [red]{last_error}[/red]")
            log.write("")
        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")

    @work(thread=True)
    def _ask_marcus(self, question: str) -> None:
        """Send a question to Marcus and display the response."""
        log = self.query_one("#activity-log", RichLog)
        log.write(f"[dim]You:[/dim] {question}")
        log.write("[dim]Marcus is thinking...[/dim]")
        try:
            result = self.sdk.agents.ask(question, mode='agent')
            response = result.get('response', '')
            if response:
                log.write("")
                log.write("[bold]Marcus:[/bold]")
                for line in response.split('\n'):
                    log.write(f"  {line}")
                log.write("")
            else:
                log.write("[yellow]No response from Marcus.[/yellow]")
        except Exception as e:
            log.write(f"[red]Marcus error: {e}[/red]")

    def action_pause_resume(self) -> None:
        if self.hunt_status == 'active':
            self._set_status('paused')
        elif self.hunt_status == 'paused':
            self._set_status('active')

    def action_stop_hunt(self) -> None:
        self._set_status('stopped')

    def action_quit(self) -> None:
        self.exit()


def _extract_hunts(resp: dict) -> list:
    """Extract hunt list from API response regardless of key name."""
    if isinstance(resp, list):
        return resp
    for key in ('hunts', 'data'):
        if key in resp and isinstance(resp[key], list):
            return resp[key]
    for key in resp:
        if isinstance(resp[key], list):
            return resp[key]
    return []


def _parse_duration_int(duration_str: str) -> int:
    """Parse duration to hours."""
    duration_str = duration_str.strip().lower()
    if duration_str.endswith('h'):
        return int(duration_str[:-1])
    if duration_str.endswith('d'):
        return int(duration_str[:-1]) * 24
    return int(duration_str)


def run_hunt_tui(sdk: Chariot, hunt_uuid: str = None, start_prompt: str = None,
                 start_duration: str = '24h', start_scope: list = None) -> None:
    """Launch the Hannibal hunt TUI."""
    app = HuntApp(sdk, hunt_uuid=hunt_uuid, start_prompt=start_prompt,
                  start_duration=start_duration, start_scope=start_scope)
    app.run()
