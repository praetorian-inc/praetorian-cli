"""Aegis credential authentication command for TUI menu."""

import re
import time

from rich.live import Live
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.text import Text

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
    """Print the full result of a completed/failed management task."""
    import json

    status = task.get('status', '')
    is_success = status == 'AMT_COMPLETED'
    color = colors['success'] if is_success else colors['error']
    label = 'Completed' if is_success else 'Failed'

    menu.console.print(f"\n  [{color}]{label}[/{color}]")

    if task.get('errorMessage'):
        menu.console.print(f"  [{colors['error']}]Error: {task['errorMessage']}[/{colors['error']}]")

    cmd = task.get('commandResult') or {}
    output_str = cmd.get('output', '')

    # Try to parse output as JSON for structured display
    output_data = None
    if output_str:
        try:
            output_data = json.loads(output_str)
        except (json.JSONDecodeError, TypeError):
            pass

    if output_data and isinstance(output_data, dict):
        # Structured output — display as key/value pairs
        max_key = max((len(str(k)) for k in output_data), default=0)
        for k, v in output_data.items():
            menu.console.print(f"  {str(k):<{max_key}}  {v}")
    else:
        # Fall back to summary fields
        if task.get('result'):
            menu.console.print(f"  Result: {task['result']}")

        if cmd:
            menu.console.print(f"  Success:   {cmd.get('success', 'N/A')}")
            menu.console.print(f"  Exit code: {cmd.get('exit_code', 'N/A')}")

        if output_str:
            menu.console.print(f"\n  [{colors['dim']}]--- Output ---[/{colors['dim']}]")
            for line in output_str.splitlines():
                menu.console.print(f"  {line}")

    if cmd.get('error_output'):
        menu.console.print(f"\n  [{colors['error']}]--- Error Output ---[/{colors['error']}]")
        for line in cmd['error_output'].splitlines():
            menu.console.print(f"  {line}")
    if cmd.get('error_message'):
        menu.console.print(f"  [{colors['error']}]Error: {cmd['error_message']}[/{colors['error']}]")


def _poll_task(menu, task_id, colors, timeout=120):
    """Poll a management task until it completes or times out."""
    start = time.monotonic()
    deadline = start + timeout
    poll_count = 0

    spinner = Spinner("dots", text=Text("  Waiting for agent to execute task...", style=colors['dim']))

    try:
        with Live(spinner, console=menu.console, refresh_per_second=10, transient=True):
            while time.monotonic() < deadline:
                time.sleep(5)
                poll_count += 1
                elapsed = int(time.monotonic() - start)

                try:
                    task = menu.sdk.aegis.get_management_task(task_id)
                except Exception:
                    spinner.update(text=Text(f"  Waiting for agent... ({elapsed}s, retrying)", style=colors['dim']))
                    continue

                current_status = task.get('status', '')

                if current_status in ('AMT_COMPLETED', 'AMT_FAILED'):
                    break

                spinner.update(text=Text(f"  Running on agent... ({elapsed}s)", style=colors['dim']))
            else:
                menu.console.print(f"  [{colors['warning']}]Timed out after {timeout}s — task may still be running[/{colors['warning']}]")
                return
    except KeyboardInterrupt:
        menu.console.print(f"\n  [{colors['dim']}]Interrupted — task may still be running in background[/{colors['dim']}]")
        return

    _print_task_result(menu, task, colors)
