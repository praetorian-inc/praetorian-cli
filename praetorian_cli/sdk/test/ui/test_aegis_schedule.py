"""Tests for schedule.py TUI command handlers."""

import pytest
from praetorian_cli.ui.aegis.commands.schedule import (
    handle_schedule,
    list_schedules,
    view_schedule,
    add_schedule,
    edit_schedule,
    delete_schedule,
    pause_schedule,
    resume_schedule,
    show_schedule_help,
    complete,
)
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockAgent

pytestmark = pytest.mark.tui


# --- Mock SDK with schedules support ---

class MockSchedulesAPI:
    """Mock for sdk.schedules that records calls."""

    def __init__(self, schedules=None, error=None):
        self._schedules = schedules or []
        self._error = error
        self.calls = []

    def list(self, pages=1):
        self.calls.append({'method': 'list'})
        if self._error:
            raise self._error
        return self._schedules, None

    def create(self, **kwargs):
        self.calls.append({'method': 'create', **kwargs})
        return {'scheduleId': 'new-schedule-id', 'status': 'active', 'nextExecution': '2024-06-15T10:00:00Z'}

    def update(self, **kwargs):
        self.calls.append({'method': 'update', **kwargs})
        return {'scheduleId': kwargs.get('schedule_id', ''), 'status': 'active', 'nextExecution': '2024-06-16T10:00:00Z'}

    def delete(self, schedule_id):
        self.calls.append({'method': 'delete', 'schedule_id': schedule_id})
        if self._error:
            raise self._error

    def pause(self, schedule_id):
        self.calls.append({'method': 'pause', 'schedule_id': schedule_id})
        if self._error:
            raise self._error
        return {'scheduleId': schedule_id, 'status': 'paused'}

    def resume(self, schedule_id):
        self.calls.append({'method': 'resume', 'schedule_id': schedule_id})
        if self._error:
            raise self._error
        return {'scheduleId': schedule_id, 'status': 'active', 'nextExecution': '2024-06-15T10:00:00Z'}


class MockAegis:
    def validate_capability(self, name):
        return {'name': name, 'description': 'test', 'target': 'asset', 'parameters': []}


class MockAssets:
    def list(self, **kwargs):
        return [], None


class ScheduleMenu(MockMenuBase):
    """Menu with schedule-specific SDK mocks."""

    def __init__(self, schedules=None, error=None):
        super().__init__()
        self.sdk = type('SDK', (), {
            'schedules': MockSchedulesAPI(schedules=schedules, error=error),
            'aegis': MockAegis(),
            'assets': MockAssets(),
        })()
        self.selected_agent = MockAgent()
        self.agent_lookup = {}


SAMPLE_SCHEDULES = [
    {
        'scheduleId': 'abc123-def456-ghi789',
        'capabilityName': 'windows-smb-snaffler',
        'status': 'active',
        'targetKey': '#asset#server01#server01',
        'clientId': 'C.1',
        'weeklySchedule': {
            'monday': {'enabled': True, 'time': '10:00'},
            'tuesday': {'enabled': False, 'time': ''},
            'wednesday': {'enabled': True, 'time': '14:00'},
            'thursday': {'enabled': False, 'time': ''},
            'friday': {'enabled': True, 'time': '10:00'},
            'saturday': {'enabled': False, 'time': ''},
            'sunday': {'enabled': False, 'time': ''},
        },
        'startDate': '2024-01-15T00:00:00Z',
        'endDate': '',
        'nextExecution': '2099-06-15T10:00:00Z',
        'lastExecution': '2024-06-14T10:00:00Z',
        'config': {'aegis': 'true', 'client_id': 'C.1'},
    },
    {
        'scheduleId': 'xyz789-uvw012',
        'capabilityName': 'linux-enum',
        'status': 'paused',
        'targetKey': '#asset#linux01#linux01',
        'clientId': '',
        'weeklySchedule': {},
        'startDate': '2024-03-01T00:00:00Z',
        'nextExecution': '',
        'config': {},
    },
]


# --- handle_schedule routing tests ---

class TestHandleScheduleRouting:
    def test_empty_args_shows_help(self):
        menu = ScheduleMenu()
        handle_schedule(menu, [])
        output = '\n'.join(menu.console.lines)
        assert 'Schedule Commands' in output

    def test_unknown_subcommand_shows_help(self):
        menu = ScheduleMenu()
        handle_schedule(menu, ['foobar'])
        output = '\n'.join(menu.console.lines)
        assert 'Unknown schedule subcommand' in output
        assert 'Schedule Commands' in output

    def test_list_subcommand_routes(self):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)
        handle_schedule(menu, ['list'])
        # list_schedules was called - verify output
        output = '\n'.join(menu.console.lines)
        assert 'Scheduled Jobs' in output


# --- list_schedules tests ---

class TestListSchedules:
    def test_list_with_schedules(self):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)
        list_schedules(menu)

        output = '\n'.join(menu.console.lines)
        assert 'Scheduled Jobs' in output
        assert menu.paused is True

    def test_list_empty_schedules(self):
        menu = ScheduleMenu(schedules=[])
        list_schedules(menu)

        output = '\n'.join(menu.console.lines)
        assert 'No scheduled jobs found' in output
        assert 'schedule add' in output
        assert menu.paused is True

    def test_list_api_error(self):
        menu = ScheduleMenu(error=Exception("API timeout"))
        list_schedules(menu)

        output = '\n'.join(menu.console.lines)
        assert 'Error listing schedules' in output
        assert menu.paused is True

    def test_list_with_agent_lookup(self):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)
        menu.agent_lookup = {'C.1': 'server01-hostname'}
        list_schedules(menu)

        # The table should be rendered (we can't easily inspect Rich Table content,
        # but the schedule list was created without error)
        assert menu.paused is True
        assert menu.sdk.schedules.calls[0]['method'] == 'list'


# --- view_schedule tests ---

class TestViewSchedule:
    def test_view_with_valid_prefix(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        # Mock interactive_schedule_picker to return the first schedule
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )

        view_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'Schedule Details' in output
        assert 'windows-smb-snaffler' in output
        assert menu.paused is True

    def test_view_not_found(self, monkeypatch):
        menu = ScheduleMenu(schedules=[])

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (None, None)
        )

        view_schedule(menu, ['nonexistent'])

        output = '\n'.join(menu.console.lines)
        assert 'not found' in output
        assert menu.paused is True

    def test_view_shows_weekly_schedule(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)
        menu.agent_lookup = {}

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )

        view_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'Schedule' in output
        assert 'Mon' in output
        assert menu.paused is True

    def test_view_hides_password_in_config(self, monkeypatch):
        schedule_with_secret = dict(SAMPLE_SCHEDULES[0])
        schedule_with_secret['config'] = {'password': 'secret123', 'aegis': 'true'}

        menu = ScheduleMenu()
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (schedule_with_secret, 'abc123')
        )

        view_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'secret123' not in output
        assert '********' in output


# --- delete_schedule tests ---

class TestDeleteSchedule:
    def test_delete_confirmed(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Confirm.ask',
            lambda *a, **k: True
        )

        delete_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'deleted successfully' in output
        assert any(c['method'] == 'delete' for c in menu.sdk.schedules.calls)

    def test_delete_cancelled(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Confirm.ask',
            lambda *a, **k: False
        )

        delete_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'Cancelled' in output
        assert not any(c['method'] == 'delete' for c in menu.sdk.schedules.calls)

    def test_delete_not_found(self, monkeypatch):
        menu = ScheduleMenu()

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (None, None)
        )

        delete_schedule(menu, ['nonexistent'])

        output = '\n'.join(menu.console.lines)
        assert 'not found' in output


# --- pause_schedule tests ---

class TestPauseSchedule:
    def test_pause_success(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )

        pause_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'paused' in output
        assert any(c['method'] == 'pause' for c in menu.sdk.schedules.calls)

    def test_pause_not_found(self, monkeypatch):
        menu = ScheduleMenu()

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (None, None)
        )

        pause_schedule(menu, ['nonexistent'])

        output = '\n'.join(menu.console.lines)
        assert 'not found' in output


# --- resume_schedule tests ---

class TestResumeSchedule:
    def test_resume_success(self, monkeypatch):
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[1], 'xyz789-uvw012')
        )

        resume_schedule(menu, ['xyz789'])

        output = '\n'.join(menu.console.lines)
        assert 'resumed' in output
        assert any(c['method'] == 'resume' for c in menu.sdk.schedules.calls)

    def test_resume_not_found(self, monkeypatch):
        menu = ScheduleMenu()

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (None, None)
        )

        resume_schedule(menu, ['nonexistent'])

        output = '\n'.join(menu.console.lines)
        assert 'not found' in output

    def test_resume_api_error(self, monkeypatch):
        menu = ScheduleMenu()
        menu.sdk.schedules._error = Exception("API unavailable")

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[1], 'xyz789-uvw012')
        )

        resume_schedule(menu, ['xyz789'])

        output = '\n'.join(menu.console.lines)
        assert 'Error resuming schedule' in output


# --- edit_schedule tests ---

class TestEditSchedule:
    def test_edit_no_changes(self, monkeypatch):
        """When user declines all edit prompts, no update is sent."""
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )
        # Decline editing weekly, start date, end date
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Confirm.ask',
            lambda *a, **k: False
        )

        from praetorian_cli.ui.aegis.commands.schedule import edit_schedule
        edit_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'No changes made' in output
        assert not any(c['method'] == 'update' for c in menu.sdk.schedules.calls)

    def test_edit_not_found(self, monkeypatch):
        menu = ScheduleMenu()

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (None, None)
        )

        edit_schedule(menu, ['nonexistent'])

        output = '\n'.join(menu.console.lines)
        assert 'not found' in output

    def test_edit_with_weekly_schedule_change(self, monkeypatch):
        """When user edits the weekly schedule, update() is called with new schedule."""
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.interactive_schedule_picker',
            lambda m, suggested, prompt_prefix: (SAMPLE_SCHEDULES[0], 'abc123-def456-ghi789')
        )

        new_weekly = {
            'monday': {'enabled': True, 'time': '08:00'},
            'tuesday': {'enabled': False, 'time': ''},
            'wednesday': {'enabled': False, 'time': ''},
            'thursday': {'enabled': True, 'time': '12:00'},
            'friday': {'enabled': False, 'time': ''},
            'saturday': {'enabled': False, 'time': ''},
            'sunday': {'enabled': False, 'time': ''},
        }

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.configure_weekly_schedule',
            lambda m: new_weekly
        )

        # Sequence: Yes to edit weekly, No to start date, No to end date, Yes to save
        confirm_answers = iter([True, False, False, True])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Confirm.ask',
            lambda *a, **k: next(confirm_answers)
        )

        edit_schedule(menu, ['abc123'])

        output = '\n'.join(menu.console.lines)
        assert 'updated successfully' in output
        update_calls = [c for c in menu.sdk.schedules.calls if c['method'] == 'update']
        assert len(update_calls) == 1
        assert update_calls[0]['schedule_id'] == 'abc123-def456-ghi789'
        assert update_calls[0]['weekly_schedule'] == new_weekly


# --- add_schedule tests ---

class TestAddSchedule:
    def test_add_schedule_success(self, monkeypatch):
        """Happy path: add_schedule creates a schedule with correct params."""
        menu = ScheduleMenu(schedules=SAMPLE_SCHEDULES)

        # Mock capability picker to return a capability name
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule._interactive_capability_picker',
            lambda m: 'windows-smb-snaffler'
        )

        new_weekly = {
            'monday': {'enabled': True, 'time': '09:00'},
            'tuesday': {'enabled': False, 'time': ''},
            'wednesday': {'enabled': True, 'time': '09:00'},
            'thursday': {'enabled': False, 'time': ''},
            'friday': {'enabled': True, 'time': '09:00'},
            'saturday': {'enabled': False, 'time': ''},
            'sunday': {'enabled': False, 'time': ''},
        }

        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.configure_weekly_schedule',
            lambda m: new_weekly
        )

        # Prompt.ask for start_date and end_date
        prompt_answers = iter(['2024-06-01T00:00:00Z', ''])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Prompt.ask',
            lambda *a, **k: next(prompt_answers)
        )

        # Confirm.ask for "Create this schedule?"
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule.Confirm.ask',
            lambda *a, **k: True
        )

        add_schedule(menu)

        output = '\n'.join(menu.console.lines)
        assert 'created successfully' in output

        create_calls = [c for c in menu.sdk.schedules.calls if c['method'] == 'create']
        assert len(create_calls) == 1
        assert create_calls[0]['capability_name'] == 'windows-smb-snaffler'
        assert create_calls[0]['weekly_schedule'] == new_weekly
        assert create_calls[0]['client_id'] == 'C.1'


# --- complete() autocomplete tests ---

class TestComplete:
    def test_complete_subcommands(self):
        menu = ScheduleMenu()
        results = complete(menu, 'li', ['schedule', 'li'])
        assert 'list' in results

    def test_complete_empty_returns_all_subcommands(self):
        menu = ScheduleMenu()
        results = complete(menu, '', ['schedule', ''])
        assert 'list' in results
        assert 'view' in results
        assert 'add' in results
        assert 'edit' in results
        assert 'delete' in results
        assert 'pause' in results
        assert 'resume' in results

    def test_complete_no_match(self):
        menu = ScheduleMenu()
        results = complete(menu, 'zzz', ['schedule', 'zzz'])
        assert len(results) == 0


# --- show_schedule_help tests ---

class TestShowScheduleHelp:
    def test_help_shows_all_subcommands(self):
        menu = ScheduleMenu()
        show_schedule_help(menu)

        output = '\n'.join(menu.console.lines)
        assert 'schedule list' in output
        assert 'schedule view' in output
        assert 'schedule add' in output
        assert 'schedule edit' in output
        assert 'schedule delete' in output
        assert 'schedule pause' in output
        assert 'schedule resume' in output
        assert menu.paused is True
