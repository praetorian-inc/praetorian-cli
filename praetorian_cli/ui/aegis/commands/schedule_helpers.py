"""Helper functions for schedule commands - formatters, completers, and interactive pickers."""

import time
from datetime import datetime, timezone
from rich.prompt import Prompt
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
from ..constants import DEFAULT_COLORS


DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DAY_ABBREVS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


# --- Formatting helpers ---

def format_target(target_key):
    """Format target key for display."""
    if not target_key:
        return 'N/A'
    parts = target_key.split('#')
    if len(parts) >= 3:
        target_type = parts[1]
        target_name = parts[2]
        return f"{target_type}: {target_name}"
    return target_key


def format_days(weekly_schedule):
    """Format weekly schedule days for compact display."""
    if not weekly_schedule:
        return 'None'
    enabled = []
    for day, abbrev in zip(DAYS, DAY_ABBREVS):
        day_sched = weekly_schedule.get(day, {})
        if day_sched.get('enabled'):
            enabled.append(abbrev[:2])
    return ' '.join(enabled) if enabled else 'None'


def format_status(status, colors):
    """Format status with color."""
    status = status.lower() if status else 'unknown'
    if status == 'active':
        return f"[{colors['success']}]●[/{colors['success']}] active"
    elif status == 'paused':
        return f"[{colors['warning']}]◐[/{colors['warning']}] paused"
    elif status == 'expired':
        return f"[{colors['dim']}]○[/{colors['dim']}] expired"
    return f"[{colors['dim']}]?[/{colors['dim']}] {status}"


def format_next_execution(next_exec):
    """Format next execution time for display."""
    if not next_exec:
        return 'Not scheduled'
    try:
        dt = datetime.fromisoformat(next_exec.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = dt - now

        if diff.total_seconds() < 0:
            return 'Overdue'
        elif diff.days == 0:
            hours = int(diff.total_seconds() // 3600)
            if hours == 0:
                minutes = int(diff.total_seconds() // 60)
                return f"in {minutes}m"
            return f"in {hours}h"
        elif diff.days == 1:
            return 'Tomorrow'
        elif diff.days < 7:
            return dt.strftime('%a %H:%M')
        else:
            return dt.strftime('%Y-%m-%d')
    except Exception:
        return next_exec[:16]


def format_date(date_str):
    """Format date string for display."""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return date_str[:10]


def format_datetime(dt_str):
    """Format datetime string for display."""
    if not dt_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return dt_str[:19]


# --- Interactive helpers ---

def configure_weekly_schedule(menu):
    """Interactively configure weekly schedule."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    weekly = {}

    menu.console.print(f"  [{colors['dim']}]Enter time in HH:MM format (24-hour UTC), or leave empty to skip day[/{colors['dim']}]")

    for day, abbrev in zip(DAYS, DAY_ABBREVS):
        time_input = Prompt.ask(f"  {abbrev}", default="")
        if time_input.strip():
            # Validate time format
            try:
                parts = time_input.split(':')
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    weekly[day] = {'enabled': True, 'time': f"{hour:02d}:{minute:02d}"}
                else:
                    menu.console.print(f"    [{colors['warning']}]Invalid time, skipping {abbrev}[/{colors['warning']}]")
                    weekly[day] = {'enabled': False, 'time': ''}
            except (ValueError, IndexError):
                menu.console.print(f"    [{colors['warning']}]Invalid format, skipping {abbrev}[/{colors['warning']}]")
                weekly[day] = {'enabled': False, 'time': ''}
        else:
            weekly[day] = {'enabled': False, 'time': ''}

    # Check at least one day is enabled
    if not any(d.get('enabled') for d in weekly.values()):
        menu.console.print(f"  [{colors['error']}]At least one day must be enabled[/{colors['error']}]")
        return None

    return weekly


# --- Completers ---

class ScheduleCompleter(Completer):
    """Custom completer for schedules with metadata display."""

    def __init__(self, schedules, agent_lookup=None):
        """Initialize with list of schedule dicts from API."""
        self.schedules = schedules
        self.agent_lookup = agent_lookup or {}

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()

        for schedule in self.schedules:
            schedule_id = schedule.get('scheduleId', '')
            capability = schedule.get('capabilityName', 'unknown')
            status = schedule.get('status', 'unknown')
            target_key = schedule.get('targetKey', '')
            client_id = schedule.get('clientId', '')

            # Get agent hostname from lookup
            agent_name = self.agent_lookup.get(client_id, '') if client_id else ''

            # Parse target for display
            target_parts = target_key.split('#') if target_key else []
            target_display = target_parts[2] if len(target_parts) >= 3 else ''

            # Short ID for display
            short_id = schedule_id[:10] if schedule_id else ''

            # Build searchable text
            searchable = f"{short_id} {capability} {status} {agent_name} {target_display}".lower()

            # Check if input matches
            if not text or text in searchable:
                # Format: id  capability  [status]  agent/target
                location = agent_name or target_display or 'N/A'
                display_meta = f"{capability[:25]:<25} [{status}] {location}"

                yield Completion(
                    schedule_id,
                    start_position=-len(document.text_before_cursor),
                    display=short_id,
                    display_meta=display_meta,
                )


# --- Schedule lookup and picker ---

def get_cached_schedules(menu):
    """Return schedules from a 30-second TTL cache on *menu*, refreshing from the API as needed."""
    cache = getattr(menu, '_schedule_cache', {'ts': 0, 'items': []})
    now = time.time()
    if now - cache['ts'] > 30 or not cache['items']:
        schedules, _ = menu.sdk.schedules.list()
        cache['items'] = schedules or []
        cache['ts'] = now
        menu._schedule_cache = cache
    return cache['items']


def invalidate_schedule_cache(menu):
    """Invalidate the schedule cache so the next read fetches fresh data from the API."""
    menu._schedule_cache = {'ts': 0, 'items': []}


def find_schedule_by_prefix(menu, prefix, schedules=None):
    """Find a schedule by ID prefix. Returns (schedule, full_id) or (None, None).

    If *schedules* is provided, searches that list instead of calling the API.
    """
    try:
        if schedules is None:
            schedules, _ = menu.sdk.schedules.list()
        for schedule in schedules:
            schedule_id = schedule.get('scheduleId', '')
            if schedule_id.startswith(prefix):
                return schedule, schedule_id
        return None, None
    except Exception:
        return None, None


def interactive_schedule_picker(menu, suggested=None, prompt_prefix="schedule"):
    """Interactive schedule picker with fuzzy search.

    If suggested is provided and matches a schedule prefix, returns it directly.
    Otherwise shows an inline fuzzy picker.
    """
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        # Fetch once and reuse for both prefix lookup and picker
        schedules, _ = menu.sdk.schedules.list()

        if suggested:
            # Check if suggested is a valid prefix - use directly without confirmation
            schedule, full_id = find_schedule_by_prefix(menu, suggested, schedules=schedules)
            if schedule:
                return schedule, full_id

        if not schedules:
            menu.console.print("  No schedules available.")
            return None, None

        # Sort by capability name
        schedules.sort(key=lambda x: x.get('capabilityName', ''))

        # Get agent lookup for display
        agent_lookup = getattr(menu, 'agent_lookup', {})

        # Create fuzzy completer
        base_completer = ScheduleCompleter(schedules, agent_lookup)
        fuzzy_completer = FuzzyCompleter(base_completer)

        try:
            # Inline prompt - appears right after the command
            result = pt_prompt(
                f"{prompt_prefix} ",
                completer=fuzzy_completer,
                complete_while_typing=True,
            )

            if result and result.strip():
                schedule_id = result.strip()
                # Find the full schedule object
                for s in schedules:
                    if s.get('scheduleId') == schedule_id:
                        return s, schedule_id
                # If exact match failed, try prefix (reuse already-fetched list)
                return find_schedule_by_prefix(menu, schedule_id, schedules=schedules)
            else:
                menu.console.print("  Cancelled.")
                return None, None

        except KeyboardInterrupt:
            menu.console.print("\n  Cancelled")
            return None, None
        except EOFError:
            menu.console.print("\n  Cancelled")
            return None, None

    except Exception as e:
        menu.console.print(f"  Error loading schedules: {e}")
        schedule_id = Prompt.ask("  Enter schedule ID manually")
        if schedule_id:
            return find_schedule_by_prefix(menu, schedule_id)
        return None, None


def complete_schedule_ids(menu, text):
    """Return schedule IDs matching the prefix for tab completion (cached)."""
    try:
        schedules = get_cached_schedules(menu)
        if not schedules:
            return []

        agent_lookup = getattr(menu, 'agent_lookup', {})
        options = []

        for schedule in schedules:
            schedule_id = schedule.get('scheduleId', '')
            capability = schedule.get('capabilityName', '')
            client_id = schedule.get('clientId', '')
            agent_name = agent_lookup.get(client_id, '') if client_id else ''

            # Use short ID for completion
            short_id = schedule_id[:10] if schedule_id else ''

            # Match against ID prefix
            if short_id.lower().startswith(text.lower()):
                options.append(short_id)
            # Also match against capability name for convenience
            elif capability.lower().startswith(text.lower()):
                options.append(short_id)
            # And agent name
            elif agent_name and agent_name.lower().startswith(text.lower()):
                options.append(short_id)

        return options
    except Exception:
        return []
