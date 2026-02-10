"""Schedule command handlers for Aegis TUI."""

from datetime import datetime, timezone
from rich.table import Table
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from ..constants import DEFAULT_COLORS
from .schedule_helpers import (
    DAYS, DAY_ABBREVS,
    format_target, format_days, format_status,
    format_next_execution, format_date, format_datetime,
    configure_weekly_schedule, interactive_schedule_picker,
    complete_schedule_ids, invalidate_schedule_cache,
)
from .job_helpers import (
    interactive_capability_picker,
    select_domain,
    select_credentials,
    configure_parameters,
    capability_needs_credentials,
    resolve_addomain_target_key,
)


def handle_schedule(menu, args):
    """Handle schedule command with subcommands: list, view, add, edit, delete, pause, resume."""
    if not args:
        show_schedule_help(menu)
        return

    subcommand = args[0].lower()
    if subcommand == 'list':
        list_schedules(menu)
    elif subcommand == 'view':
        view_schedule(menu, args[1:])
    elif subcommand == 'add':
        add_schedule(menu)
    elif subcommand == 'edit':
        edit_schedule(menu, args[1:])
    elif subcommand == 'delete':
        delete_schedule(menu, args[1:])
    elif subcommand == 'pause':
        pause_schedule(menu, args[1:])
    elif subcommand == 'resume':
        resume_schedule(menu, args[1:])
    else:
        menu.console.print(f"\n  Unknown schedule subcommand: {subcommand}")
        show_schedule_help(menu)


def show_schedule_help(menu):
    help_text = """
  Schedule Commands

  schedule list                   List all scheduled jobs
  schedule view [id]              View schedule details (interactive picker)
  schedule add                    Create a new scheduled job (interactive)
  schedule edit [id]              Edit an existing schedule (interactive picker)
  schedule delete [id]            Delete a schedule (interactive picker)
  schedule pause [id]             Pause a schedule (interactive picker)
  schedule resume [id]            Resume a paused schedule (interactive picker)

  Examples:
    schedule list                  # List all schedules
    schedule view                  # Interactive fuzzy picker to select schedule
    schedule view abc123           # View schedule by ID prefix
    schedule add                   # Create new schedule interactively
    schedule edit                  # Interactive fuzzy picker then edit
    schedule edit abc123           # Edit schedule by ID prefix
    schedule delete abc123         # Delete schedule
    schedule pause abc123          # Pause schedule
    schedule resume abc123         # Resume paused schedule
"""
    menu.console.print(help_text)
    menu.pause()


def list_schedules(menu):
    """List all schedules for the current user."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    try:
        schedules, _ = menu.sdk.schedules.list()

        if not schedules:
            menu.console.print("\n  No scheduled jobs found\n")
            menu.console.print("  Use 'schedule add' to create one.\n")
            menu.pause()
            return

        # Sort by next execution time
        schedules.sort(key=lambda s: s.get('nextExecution', '') or 'zzz')

        # Use cached agent lookup from menu (built when agents were loaded)
        agent_lookup = getattr(menu, 'agent_lookup', {})
        table = Table(
            show_header=True,
            header_style=f"bold {colors['primary']}",
            border_style=colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )

        table.add_column("ID", style=f"bold {colors['accent']}", width=10, no_wrap=True)
        table.add_column("CAPABILITY", style="white", min_width=20, no_wrap=True)
        table.add_column("AGENT", style=f"{colors['success']}", min_width=15, no_wrap=True)
        table.add_column("TARGET", style=f"{colors['dim']}", min_width=15, no_wrap=True)
        table.add_column("DAYS", style="white", width=21, no_wrap=True)
        table.add_column("STATUS", width=8, justify="center", no_wrap=True)
        table.add_column("NEXT RUN", style=f"{colors['dim']}", width=12, justify="right", no_wrap=True)

        menu.console.print()
        menu.console.print("  Scheduled Jobs")
        menu.console.print()

        for schedule in schedules:
            schedule_id = schedule.get('scheduleId', '')[:10]
            capability = schedule.get('capabilityName', 'unknown')
            target_key = schedule.get('targetKey', '')
            status = schedule.get('status', 'unknown')
            next_exec = schedule.get('nextExecution', '')
            client_id = schedule.get('clientId', '')

            # Get agent hostname from lookup, fall back to client_id or config
            if client_id and client_id in agent_lookup:
                agent_display = agent_lookup[client_id]
            elif client_id:
                # Show shortened client_id if no hostname found
                agent_display = client_id[:15] + '...' if len(client_id) > 15 else client_id
            else:
                # Try to get from config
                config = schedule.get('config', {})
                client_id_from_config = config.get('client_id', '')
                if client_id_from_config and client_id_from_config in agent_lookup:
                    agent_display = agent_lookup[client_id_from_config]
                elif client_id_from_config:
                    agent_display = client_id_from_config[:15] + '...' if len(client_id_from_config) > 15 else client_id_from_config
                else:
                    agent_display = '—'

            # Format target display
            target_display = format_target(target_key)

            # Format days display
            days_display = format_days(schedule.get('weeklySchedule', {}))

            # Format status with color
            status_display = format_status(status, colors)

            # Format next execution
            next_display = format_next_execution(next_exec)

            table.add_row(schedule_id, capability, agent_display, target_display, days_display, status_display, next_display)

        menu.console.print(table)
        menu.console.print()
        menu.pause()

    except Exception as e:
        menu.console.print(f"[{colors['error']}]Error listing schedules: {e}[/{colors['error']}]")
        menu.pause()


def view_schedule(menu, args):
    """View detailed information about a schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    # Use interactive picker if no ID provided, otherwise validate the provided one
    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule view")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  Schedule not found: {suggested_id}")
        menu.pause()
        return

    try:
        # Use cached agent lookup from menu
        agent_lookup = getattr(menu, 'agent_lookup', {})

        menu.console.print()
        menu.console.print(f"  [bold {colors['primary']}]Schedule Details[/]")
        menu.console.print()
        menu.console.print(f"  ID:            {schedule.get('scheduleId', 'N/A')}")
        menu.console.print(f"  Capability:    {schedule.get('capabilityName', 'N/A')}")
        menu.console.print(f"  Target:        {schedule.get('targetKey', 'N/A')}")
        menu.console.print(f"  Status:        {format_status(schedule.get('status', 'unknown'), colors)}")

        # Show agent information
        client_id = schedule.get('clientId', '')
        if not client_id:
            config = schedule.get('config', {})
            client_id = config.get('client_id', '')

        if client_id:
            agent_hostname = agent_lookup.get(client_id, '')
            if agent_hostname:
                menu.console.print(f"  Agent:         [{colors['success']}]{agent_hostname}[/{colors['success']}]")
                menu.console.print(f"  Client ID:     [{colors['dim']}]{client_id}[/{colors['dim']}]")
            else:
                menu.console.print(f"  Client ID:     {client_id}")

        menu.console.print()
        menu.console.print(f"  [bold {colors['primary']}]Schedule[/]")
        weekly = schedule.get('weeklySchedule', {})
        for day, abbrev in zip(DAYS, DAY_ABBREVS):
            day_sched = weekly.get(day, {})
            if day_sched.get('enabled'):
                time_str = day_sched.get('time', 'N/A')
                menu.console.print(f"    {abbrev}: [{colors['success']}]✓ {time_str} UTC[/{colors['success']}]")
            else:
                menu.console.print(f"    {abbrev}: [{colors['dim']}]—[/{colors['dim']}]")

        menu.console.print()
        menu.console.print(f"  [bold {colors['primary']}]Dates[/]")
        menu.console.print(f"  Start:         {format_date(schedule.get('startDate', ''))}")
        end_date = schedule.get('endDate', '')
        menu.console.print(f"  End:           {format_date(end_date) if end_date else 'No end date'}")

        menu.console.print()
        menu.console.print(f"  [bold {colors['primary']}]Execution[/]")
        next_exec = schedule.get('nextExecution', '')
        last_exec = schedule.get('lastExecution', '')
        menu.console.print(f"  Next:          {format_datetime(next_exec) if next_exec else 'Not scheduled'}")
        menu.console.print(f"  Last:          {format_datetime(last_exec) if last_exec else 'Never'}")

        # Show config if present
        config = schedule.get('config', {})
        if config:
            menu.console.print()
            menu.console.print(f"  [bold {colors['primary']}]Configuration[/]")
            for key, value in config.items():
                # Hide sensitive values
                if 'password' in key.lower() or 'secret' in key.lower():
                    value = '********'
                menu.console.print(f"    {key}: {value}")

        menu.console.print()
        menu.pause()

    except Exception as e:
        menu.console.print(f"[{colors['error']}]Error viewing schedule: {e}[/{colors['error']}]")
        menu.pause()


def add_schedule(menu):
    """Interactively create a new schedule."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    menu.console.print(f"\n  [bold {colors['primary']}]Create New Schedule[/bold {colors['primary']}]\n")

    # Select capability
    capability = interactive_capability_picker(menu)
    if not capability:
        return

    # Get capability info
    capability_info = menu.sdk.aegis.validate_capability(capability)
    if not capability_info:
        menu.console.print(f"  [{colors['error']}]Invalid capability: '{capability}'[/{colors['error']}]")
        menu.pause()
        return

    target_type = capability_info.get('target', 'asset').lower()
    hostname = menu.selected_agent.hostname or 'Unknown'

    # Create target key
    if target_type == 'addomain':
        domain = select_domain(menu)
        if not domain:
            return

        target_key = resolve_addomain_target_key(menu, domain)
        if not target_key:
            menu.console.print(f"  [{colors['error']}]No asset found for domain '{domain}'.[/{colors['error']}]")
            menu.console.print(f"  [{colors['dim']}]The domain must exist as an asset before scheduling jobs against it.[/{colors['dim']}]")
            menu.console.print(f"  [{colors['dim']}]Add it first with: praetorian chariot add asset --dns {domain} --type addomain[/{colors['dim']}]")
            menu.pause()
            return

        target_display = f"domain {domain}"
    else:
        target_key = f"#asset#{hostname}#{hostname}"
        target_display = f"asset {hostname}"

    menu.console.print(f"  Target: {target_display}")

    # Configure weekly schedule
    menu.console.print(f"\n  [{colors['dim']}]Configure weekly schedule (24-hour UTC times)[/{colors['dim']}]")
    weekly_schedule = configure_weekly_schedule(menu)
    if not weekly_schedule:
        menu.console.print("  Cancelled\n")
        menu.pause()
        return

    # Configure start date
    now = datetime.now(timezone.utc)
    default_start = now.strftime('%Y-%m-%dT00:00:00Z')
    start_date = Prompt.ask("  Start date (RFC3339)", default=default_start)

    # Configure end date
    end_date = Prompt.ask("  End date (RFC3339, leave empty for no end)", default="")

    # Configure parameters
    config = {}
    config['aegis'] = 'true'
    config['client_id'] = menu.selected_agent.client_id or ''
    config['manual'] = 'true'

    # Handle credentials if needed
    if capability_needs_credentials(capability_info):
        if Confirm.ask("  This capability may require credentials. Add them?"):
            credential_key, _ = select_credentials(menu)
            if credential_key:
                parts = credential_key.split('#')
                if len(parts) >= 5:
                    config['credential_id'] = parts[-1]

    # Handle large artifact storage - always offer the option
    # Default to True if capability metadata says it supports it, or if capability name suggests large output
    capability_suggests_large = capability_info.get('largeArtifact', False) or any(
        keyword in capability.lower() for keyword in ['snaffler', 'bloodhound', 'sharphound', 'umber', 'dump', 'collect', 'extract']
    )
    if Confirm.ask("  Enable large artifact storage? (Results will be uploaded to S3)", default=capability_suggests_large):
        config['largeArtifact'] = 'true'

    # Optional parameters
    custom_params = configure_parameters(menu, capability_info, has_credential=bool(config.get('credential_id')))
    if custom_params:
        config.update(custom_params)

    # Confirm
    menu.console.print(f"\n  [bold {colors['primary']}]Summary[/]")
    menu.console.print(f"  Capability: {capability}")
    menu.console.print(f"  Target: {target_display}")
    menu.console.print(f"  Days: {format_days(weekly_schedule)}")
    menu.console.print(f"  Start: {start_date}")
    if end_date:
        menu.console.print(f"  End: {end_date}")

    if not Confirm.ask("\n  Create this schedule?"):
        menu.console.print("  Cancelled\n")
        menu.pause()
        return

    try:
        result = menu.sdk.schedules.create(
            capability_name=capability,
            target_key=target_key,
            weekly_schedule=weekly_schedule,
            start_date=start_date,
            end_date=end_date if end_date else None,
            config=config,
            client_id=menu.selected_agent.client_id
        )

        invalidate_schedule_cache(menu)
        schedule_id = result.get('scheduleId', 'unknown')
        menu.console.print(f"\n  [{colors['success']}]✓ Schedule created successfully[/{colors['success']}]")
        menu.console.print(f"  Schedule ID: {schedule_id}")
        menu.console.print(f"  Next execution: {format_datetime(result.get('nextExecution', ''))}")

    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Error creating schedule: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def edit_schedule(menu, args):
    """Edit an existing schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    # Use interactive picker if no ID provided, otherwise validate the provided one
    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule edit")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  Schedule not found: {suggested_id}")
        menu.pause()
        return

    try:
        menu.console.print(f"\n  [bold {colors['primary']}]Edit Schedule: {schedule_id[:10]}[/]")
        menu.console.print(f"  Capability: {schedule.get('capabilityName', 'N/A')}")
        menu.console.print()

        # Edit weekly schedule
        if Confirm.ask("  Edit weekly schedule?"):
            weekly_schedule = configure_weekly_schedule(menu)
            if not weekly_schedule:
                menu.console.print("  Schedule edit cancelled\n")
                menu.pause()
                return
        else:
            weekly_schedule = None

        # Edit start date
        current_start = schedule.get('startDate', '')
        if Confirm.ask("  Edit start date?"):
            start_date = Prompt.ask("  Start date (RFC3339)", default=current_start)
        else:
            start_date = None

        # Edit end date
        current_end = schedule.get('endDate', '')
        if Confirm.ask("  Edit end date?"):
            end_date = Prompt.ask("  End date (RFC3339, empty to remove)", default=current_end)
        else:
            end_date = None

        # Confirm changes
        if weekly_schedule is None and start_date is None and end_date is None:
            menu.console.print("  No changes made.\n")
            menu.pause()
            return

        if not Confirm.ask("\n  Save changes?"):
            menu.console.print("  Cancelled\n")
            menu.pause()
            return

        result = menu.sdk.schedules.update(
            schedule_id=schedule_id,
            weekly_schedule=weekly_schedule,
            start_date=start_date,
            end_date=end_date
        )

        invalidate_schedule_cache(menu)
        menu.console.print(f"\n[{colors['success']}]✓ Schedule updated successfully[/{colors['success']}]")
        menu.console.print(f"  Next execution: {format_datetime(result.get('nextExecution', ''))}")

    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Error updating schedule: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def delete_schedule(menu, args):
    """Delete a schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    # Use interactive picker if no ID provided, otherwise validate the provided one
    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule delete")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  Schedule not found: {suggested_id}")
        menu.pause()
        return

    try:
        menu.console.print(f"\n  Schedule: {schedule_id[:10]}")
        menu.console.print(f"  Capability: {schedule.get('capabilityName', 'N/A')}")
        menu.console.print(f"  Target: {format_target(schedule.get('targetKey', ''))}")

        if not Confirm.ask(f"\n  [{colors['error']}]Delete this schedule?[/{colors['error']}]"):
            menu.console.print("  Cancelled\n")
            menu.pause()
            return

        menu.sdk.schedules.delete(schedule_id)
        invalidate_schedule_cache(menu)
        menu.console.print(f"\n[{colors['success']}]✓ Schedule deleted successfully[/{colors['success']}]")

    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Error deleting schedule: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def pause_schedule(menu, args):
    """Pause a schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    # Use interactive picker if no ID provided, otherwise validate the provided one
    suggested_id = args[0] if args else None
    schedule, full_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule pause")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n[{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    try:
        result = menu.sdk.schedules.pause(full_id)
        invalidate_schedule_cache(menu)
        menu.console.print(f"\n[{colors['success']}]✓ Schedule paused[/{colors['success']}]")
        menu.console.print(f"  Status: {result.get('status', 'paused')}")

    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Error pausing schedule: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def resume_schedule(menu, args):
    """Resume a paused schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    # Use interactive picker if no ID provided, otherwise validate the provided one
    suggested_id = args[0] if args else None
    schedule, full_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule resume")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n[{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    try:
        result = menu.sdk.schedules.resume(full_id)
        invalidate_schedule_cache(menu)
        menu.console.print(f"\n[{colors['success']}]✓ Schedule resumed[/{colors['success']}]")
        menu.console.print(f"  Status: {result.get('status', 'active')}")
        menu.console.print(f"  Next execution: {format_datetime(result.get('nextExecution', ''))}")

    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Error resuming schedule: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def complete(menu, text, tokens):
    """Autocomplete for schedule command."""
    sub = ['list', 'view', 'add', 'edit', 'delete', 'pause', 'resume']

    # Complete subcommands
    if len(tokens) <= 2:
        return [s for s in sub if s.startswith(text)]

    # Complete schedule IDs for commands that take them
    subcommand = tokens[1].lower() if len(tokens) > 1 else ''
    if subcommand in ['view', 'edit', 'delete', 'pause', 'resume']:
        return complete_schedule_ids(menu, text)

    return []
