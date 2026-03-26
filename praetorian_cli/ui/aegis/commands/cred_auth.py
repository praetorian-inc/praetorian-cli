"""Aegis credential authentication command for TUI menu."""

import re

from rich.live import Live
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.text import Text

from praetorian_cli.sdk.entities.aegis import parse_task_result
from ..constants import DEFAULT_COLORS
from .job_helpers import select_credentials


_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def handle_cred_auth(menu, args):
    """Run AD credential authentication on the selected agent.

    Usage:
        cred-auth                Interactive credential picker, waits for result
        cred-auth <uuid>         Authenticate with a specific credential UUID
        cred-auth --no-wait      Submit task without waiting for completion
    """
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    if not menu.selected_agent:
        menu.console.print(f"  [{colors['error']}]No agent selected. Use 'set <id>' first.[/{colors['error']}]")
        menu.pause()
        return

    agent = menu.selected_agent
    no_wait = '--no-wait' in args
    filtered_args = [a for a in args if a not in ('--no-wait', '--wait')]

    # Get credential UUID — from argument or interactive picker
    credential_id = None
    if filtered_args:
        candidate = filtered_args[0]
        if _UUID_RE.match(candidate):
            credential_id = candidate
        else:
            menu.console.print(f"  [{colors['error']}]Invalid credential UUID: {candidate}[/{colors['error']}]")
            menu.pause()
            return
    else:
        # Interactive: use the existing credential picker
        credential_key, display_name = select_credentials(menu)
        if not credential_key:
            return

        # Extract UUID from credential key: #credential#{category}#{type}#{uuid}
        parts = credential_key.split('#')
        # Find the UUID part (last segment that matches UUID format)
        for part in reversed(parts):
            if _UUID_RE.match(part):
                credential_id = part
                break

        if not credential_id:
            menu.console.print(f"  [{colors['error']}]Could not extract credential UUID from key: {credential_key}[/{colors['error']}]")
            menu.pause()
            return

    # Confirm
    menu.console.print(f"\n  [{colors['primary']}]Credential Auth[/{colors['primary']}]")
    menu.console.print(f"  Agent:      {agent.hostname} ({agent.client_id})")
    menu.console.print(f"  Credential: {credential_id}")
    menu.console.print()

    try:
        confirm = Prompt.ask("  Proceed?", choices=["y", "n"], default="y")
        if confirm.lower() != 'y':
            menu.console.print(f"  [{colors['dim']}]Cancelled[/{colors['dim']}]")
            return
    except KeyboardInterrupt:
        menu.console.print(f"\n  [{colors['dim']}]Cancelled[/{colors['dim']}]")
        return

    # Submit the management task
    try:
        result = menu.sdk.aegis.credential_auth(agent.client_id, credential_id)
        task_id = result.get('taskId', '')
        message = result.get('message', '')

        menu.console.print(f"\n  [{colors['success']}]Task submitted[/{colors['success']}]")
        if message:
            menu.console.print(f"  {message}")

    except Exception as e:
        menu.console.print(f"  [{colors['error']}]Failed to create task: {e}[/{colors['error']}]")
        menu.pause()
        return

    # Wait for completion by default
    if not no_wait and task_id:
        _poll_task(menu, task_id, colors)

    menu.console.print()
    menu.pause()


def _print_task_result(menu, task, colors):
    """Display a completed management task result in the TUI."""
    r = parse_task_result(task)
    color = colors['success'] if r['is_success'] else colors['error']
    label = 'Completed' if r['is_success'] else 'Failed'

    menu.console.print(f"\n  [{color}]{label}[/{color}]")

    if r['error_message']:
        menu.console.print(f"  [{colors['error']}]Error: {r['error_message']}[/{colors['error']}]")

    if r['output_data']:
        max_key = max((len(str(k)) for k in r['output_data']), default=0)
        for k, v in r['output_data'].items():
            menu.console.print(f"  {str(k):<{max_key}}  {v}")
    else:
        if r['result']:
            menu.console.print(f"  Result: {r['result']}")
        if r['success'] is not None or r['exit_code'] is not None:
            menu.console.print(f"  Success:   {r['success'] or 'N/A'}")
            menu.console.print(f"  Exit code: {r['exit_code'] or 'N/A'}")
        if r['output_raw']:
            menu.console.print(f"\n  [{colors['dim']}]--- Output ---[/{colors['dim']}]")
            for line in r['output_raw'].splitlines():
                menu.console.print(f"  {line}")

    if r['error_output']:
        menu.console.print(f"\n  [{colors['error']}]--- Error Output ---[/{colors['error']}]")
        for line in r['error_output'].splitlines():
            menu.console.print(f"  {line}")
    if r['command_error']:
        menu.console.print(f"  [{colors['error']}]Error: {r['command_error']}[/{colors['error']}]")


def _poll_task(menu, task_id, colors, timeout=120):
    """Poll a management task until it completes or times out."""
    spinner = Spinner("dots", text=Text("  Waiting for agent to execute task...", style=colors['dim']))

    def _on_status(elapsed, message, retrying):
        suffix = f" ({elapsed}s, retrying)" if retrying else f" ({elapsed}s)"
        spinner.update(text=Text(f"  {message}{suffix}", style=colors['dim']))

    try:
        with Live(spinner, console=menu.console, refresh_per_second=10, transient=True):
            task = menu.sdk.aegis.poll_management_task(
                task_id, timeout=timeout, on_status=_on_status,
            )
    except KeyboardInterrupt:
        menu.console.print(f"\n  [{colors['dim']}]Interrupted — task may still be running in background[/{colors['dim']}]")
        return

    if task:
        _print_task_result(menu, task, colors)
    else:
        menu.console.print(f"  [{colors['warning']}]Timed out after {timeout}s — task may still be running[/{colors['warning']}]")
