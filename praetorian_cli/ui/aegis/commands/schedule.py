"""Schedule command handlers for Aegis TUI."""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from ..constants import DEFAULT_COLORS
from praetorian_cli.sdk.entities.account_discovery import load_schedules_for_accounts, truncate_email
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
    select_asset,
    select_credentials,
    configure_parameters,
    capability_needs_credentials,
    resolve_addomain_target_key,
    extract_target_type,
)

logger = logging.getLogger(__name__)


@contextmanager
def _schedule_account_context(menu, schedule_id):
    """Context manager: assume into a schedule's account, restore on exit.

    Yields True if the tenant switch succeeded (or not in multi-account mode).
    Yields False if the account could not be resolved or assumption failed.
    Always restores the prior account context in the finally block.
    """
    if not menu.multi_account_mode:
        yield True
        return

    previous_account = menu.sdk.keychain.account
    acct_info = getattr(menu, 'schedule_account_map', {}).get(schedule_id, {})
    acct_email = acct_info.get('account_email')
    if not acct_email:
        logger.warning('No account email found for schedule %s', schedule_id[:10])
        yield False
        return

    try:
        menu.sdk.accounts.assume_role(acct_email)
    except Exception as e:
        logger.error('Failed to assume role for %s: %s', acct_email, e)
        yield False
        return

    try:
        yield True
    finally:
        if previous_account:
            try:
                menu.sdk.accounts.assume_role(previous_account)
            except Exception as e:
                logger.error('Failed to restore account %s: %s', previous_account, e)
        else:
            try:
                menu.sdk.accounts.unassume_role()
            except Exception as e:
                logger.error('Failed to unassume role: %s', e)


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
    """List all schedules for the current user (or all selected accounts in multi-account mode)."""
    colors = menu.colors
    multi_account = menu.multi_account_mode

    try:
        if multi_account and menu.selected_accounts:
            schedule_tuples, failed = load_schedules_for_accounts(menu.sdk, menu.selected_accounts)
            schedules = [s for s, _ in schedule_tuples]
            menu.schedule_account_map = {}
            for sched, acct_info in schedule_tuples:
                menu.schedule_account_map[sched.get('scheduleId', '')] = acct_info
            if failed:
                menu.console.print(f"[{colors['warning']}]Failed to load schedules for: {', '.join(failed)}[/{colors['warning']}]")
        else:
            schedules, _ = menu.sdk.schedules.list()
            menu.schedule_account_map = {}

        if not schedules:
            menu.console.print("\n  No scheduled jobs found\n")
            menu.console.print("  Use 'schedule add' to create one.\n")
            menu.pause()
            return

        schedules.sort(key=lambda s: s.get('nextExecution', '') or 'zzz')

        agent_lookup = getattr(menu, 'agent_lookup', {})
        agent_os_lookup = getattr(menu, 'agent_os_lookup', {})
        table = Table(
            show_header=True,
            header_style=f"bold {colors['primary']}",
            border_style=colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )

        if multi_account:
            table.add_column("ACCOUNT", style=f"{colors['dim']}", width=19, no_wrap=True)
            table.add_column("ACCT STATUS", width=12, no_wrap=True)

        table.add_column("ID", style=f"bold {colors['accent']}", width=10, no_wrap=True)
        table.add_column("CAPABILITY", style="white", min_width=20, no_wrap=True)
        table.add_column("AGENT", style=f"{colors['success']}", min_width=15, no_wrap=True)
        table.add_column("OS", style=f"{colors['dim']}", width=3, no_wrap=True)
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

            if client_id and client_id in agent_lookup:
                agent_display = agent_lookup[client_id]
            elif client_id:
                agent_display = truncate_email(client_id, 15)
            else:
                config = schedule.get('config', {})
                client_id_from_config = config.get('client_id', '')
                if client_id_from_config and client_id_from_config in agent_lookup:
                    agent_display = agent_lookup[client_id_from_config]
                elif client_id_from_config:
                    agent_display = truncate_email(client_id_from_config, 15)
                else:
                    agent_display = '—'

            resolved_client_id = client_id or schedule.get('config', {}).get('client_id', '')
            agent_os = agent_os_lookup.get(resolved_client_id, '').lower()
            os_display = 'WIN' if 'windows' in agent_os else 'NIX' if agent_os else '—'

            target_display = format_target(target_key)
            days_display = format_days(schedule.get('weeklySchedule', {}))
            status_display = format_status(status, colors)
            next_display = format_next_execution(next_exec)

            row_cells = []
            if multi_account:
                acct_info = menu.schedule_account_map.get(schedule.get('scheduleId', ''), {})
                acct_name = truncate_email(acct_info.get('display_name', ''), 19)
                acct_status = acct_info.get('status', '')
                acct_status_style = colors['success'] if acct_status.upper() == 'ACTIVE' else colors['dim']
                row_cells.append(Text(acct_name, style=colors['dim']))
                row_cells.append(Text(acct_status, style=acct_status_style))

            row_cells.extend([schedule_id, capability, agent_display, os_display, target_display, days_display, status_display, next_display])
            table.add_row(*row_cells)

        menu.console.print(table)
        menu.console.print()
        menu.pause()

    except Exception as e:
        menu.console.print(f"[{colors['error']}]Error listing schedules: {e}[/{colors['error']}]")
        menu.pause()


def view_schedule(menu, args):
    """View detailed information about a schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule view")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  [{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    with _schedule_account_context(menu, schedule_id) as switched:
        if not switched:
            menu.console.print(f"\n  [{colors['error']}]Could not switch to schedule's account.[/{colors['error']}]")
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

    target_type = extract_target_type(capability_info)
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
            menu.console.print(f"  [{colors['dim']}]Add it first with: praetorian chariot add asset --group {domain} --type addomain[/{colors['dim']}]")
            menu.pause()
            return

        target_display = f"domain {domain}"
    else:
        # Interactive asset selection - pick existing or enter new target
        target_key, target_display = select_asset(menu, hostname)
        if not target_key:
            return  # User cancelled

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

    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule edit")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  [{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    with _schedule_account_context(menu, schedule_id) as switched:
        if not switched:
            menu.console.print(f"\n  [{colors['error']}]Could not switch to schedule's account.[/{colors['error']}]")
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

    suggested_id = args[0] if args else None
    schedule, schedule_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule delete")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n  [{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    with _schedule_account_context(menu, schedule_id) as switched:
        if not switched:
            menu.console.print(f"\n  [{colors['error']}]Could not switch to schedule's account.[/{colors['error']}]")
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

    suggested_id = args[0] if args else None
    schedule, full_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule pause")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n[{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    with _schedule_account_context(menu, full_id) as switched:
        if not switched:
            menu.console.print(f"\n[{colors['error']}]Could not switch to schedule's account.[/{colors['error']}]")
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

    suggested_id = args[0] if args else None
    schedule, full_id = interactive_schedule_picker(menu, suggested_id, prompt_prefix="schedule resume")

    if not schedule:
        if suggested_id:
            menu.console.print(f"\n[{colors['error']}]Schedule not found: {suggested_id}[/{colors['error']}]")
        menu.pause()
        return

    with _schedule_account_context(menu, full_id) as switched:
        if not switched:
            menu.console.print(f"\n[{colors['error']}]Could not switch to schedule's account.[/{colors['error']}]")
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
