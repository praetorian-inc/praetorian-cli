"""Tests for schedule_helpers.py formatting functions and interactive helpers."""

import pytest
from praetorian_cli.ui.aegis.commands.schedule_helpers import (
    format_target,
    format_days,
    format_status,
    format_next_execution,
    format_date,
    format_datetime,
    configure_weekly_schedule,
    find_schedule_by_prefix,
    complete_schedule_ids,
    ScheduleCompleter,
    DAYS,
    DAY_ABBREVS,
)
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase

pytestmark = pytest.mark.tui


# --- format_target tests ---

class TestFormatTarget:
    def test_valid_asset_key(self):
        assert format_target('#asset#server01#server01') == 'asset: server01'

    def test_valid_addomain_key(self):
        assert format_target('#addomain#example.local#example.local') == 'addomain: example.local'

    def test_short_key_returns_as_is(self):
        assert format_target('short') == 'short'

    def test_empty_string(self):
        assert format_target('') == 'N/A'

    def test_none_input(self):
        assert format_target(None) == 'N/A'

    def test_two_part_key(self):
        assert format_target('#asset') == '#asset'


# --- format_days tests ---

class TestFormatDays:
    def test_all_days_enabled(self):
        weekly = {day: {'enabled': True, 'time': '10:00'} for day in DAYS}
        result = format_days(weekly)
        assert result == 'Mo Tu We Th Fr Sa Su'

    def test_no_days_enabled(self):
        weekly = {day: {'enabled': False, 'time': ''} for day in DAYS}
        assert format_days(weekly) == 'None'

    def test_weekdays_only(self):
        weekly = {}
        for day in DAYS:
            weekly[day] = {'enabled': day not in ['saturday', 'sunday'], 'time': '09:00'}
        result = format_days(weekly)
        assert result == 'Mo Tu We Th Fr'

    def test_empty_schedule(self):
        assert format_days({}) == 'None'

    def test_none_schedule(self):
        assert format_days(None) == 'None'

    def test_single_day(self):
        weekly = {day: {'enabled': False, 'time': ''} for day in DAYS}
        weekly['wednesday'] = {'enabled': True, 'time': '14:00'}
        result = format_days(weekly)
        assert result == 'We'


# --- format_status tests ---

class TestFormatStatus:
    COLORS = {
        'primary': 'cyan',
        'accent': 'magenta',
        'dim': 'dim',
        'success': 'green',
        'warning': 'yellow',
        'error': 'red',
    }

    def test_active_status(self):
        result = format_status('active', self.COLORS)
        assert 'active' in result
        assert self.COLORS['success'] in result

    def test_paused_status(self):
        result = format_status('paused', self.COLORS)
        assert 'paused' in result
        assert self.COLORS['warning'] in result

    def test_expired_status(self):
        result = format_status('expired', self.COLORS)
        assert 'expired' in result
        assert self.COLORS['dim'] in result

    def test_unknown_status(self):
        result = format_status('something_else', self.COLORS)
        assert 'something_else' in result

    def test_none_status(self):
        result = format_status(None, self.COLORS)
        assert 'unknown' in result

    def test_uppercase_status_normalized(self):
        result = format_status('ACTIVE', self.COLORS)
        assert 'active' in result


# --- format_date tests ---

class TestFormatDate:
    def test_valid_iso_date(self):
        assert format_date('2024-06-15T10:30:00Z') == '2024-06-15'

    def test_none_input(self):
        assert format_date(None) == 'N/A'

    def test_empty_string(self):
        assert format_date('') == 'N/A'

    def test_invalid_format_returns_truncated(self):
        result = format_date('not-a-date-at-all')
        assert result == 'not-a-date'


# --- format_datetime tests ---

class TestFormatDatetime:
    def test_valid_iso_datetime(self):
        result = format_datetime('2024-06-15T10:30:00Z')
        assert '2024-06-15' in result
        assert '10:30' in result
        assert 'UTC' in result

    def test_none_input(self):
        assert format_datetime(None) == 'N/A'

    def test_empty_string(self):
        assert format_datetime('') == 'N/A'


# --- format_next_execution tests ---

class TestFormatNextExecution:
    def test_none_input(self):
        assert format_next_execution(None) == 'Not scheduled'

    def test_empty_string(self):
        assert format_next_execution('') == 'Not scheduled'

    def test_past_time_shows_overdue(self):
        result = format_next_execution('2020-01-01T00:00:00Z')
        assert result == 'Overdue'

    def test_far_future_shows_date(self):
        result = format_next_execution('2099-12-31T23:59:00Z')
        assert '2099-12-31' in result


# --- configure_weekly_schedule tests ---

class TestConfigureWeeklySchedule:
    def test_all_days_configured(self, monkeypatch):
        menu = MockMenuBase()
        # Mock Prompt.ask to return times for weekdays, empty for weekends
        times = iter(['09:00', '09:00', '09:00', '09:00', '09:00', '', ''])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule_helpers.Prompt.ask',
            lambda *a, **k: next(times)
        )

        result = configure_weekly_schedule(menu)
        assert result is not None
        assert result['monday']['enabled'] is True
        assert result['monday']['time'] == '09:00'
        assert result['saturday']['enabled'] is False
        assert result['sunday']['enabled'] is False

    def test_no_days_enabled_returns_none(self, monkeypatch):
        menu = MockMenuBase()
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule_helpers.Prompt.ask',
            lambda *a, **k: ''
        )

        result = configure_weekly_schedule(menu)
        assert result is None

    def test_invalid_time_format_skipped(self, monkeypatch):
        menu = MockMenuBase()
        # First day gets invalid time, second gets valid, rest empty
        times = iter(['abc', '14:30', '', '', '', '', ''])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule_helpers.Prompt.ask',
            lambda *a, **k: next(times)
        )

        result = configure_weekly_schedule(menu)
        assert result is not None
        assert result['monday']['enabled'] is False
        assert result['tuesday']['enabled'] is True
        assert result['tuesday']['time'] == '14:30'

    def test_out_of_range_time_skipped(self, monkeypatch):
        menu = MockMenuBase()
        # Hour 25 is invalid
        times = iter(['25:00', '10:00', '', '', '', '', ''])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule_helpers.Prompt.ask',
            lambda *a, **k: next(times)
        )

        result = configure_weekly_schedule(menu)
        assert result['monday']['enabled'] is False
        assert result['tuesday']['enabled'] is True

    def test_hour_only_input(self, monkeypatch):
        menu = MockMenuBase()
        # "10" without minutes should be treated as 10:00
        times = iter(['10', '', '', '', '', '', ''])
        monkeypatch.setattr(
            'praetorian_cli.ui.aegis.commands.schedule_helpers.Prompt.ask',
            lambda *a, **k: next(times)
        )

        result = configure_weekly_schedule(menu)
        assert result['monday']['enabled'] is True
        assert result['monday']['time'] == '10:00'


# --- ScheduleCompleter tests ---

class TestScheduleCompleter:
    def test_completions_returned_for_matching_input(self):
        schedules = [
            {
                'scheduleId': 'abc123-def456',
                'capabilityName': 'windows-smb',
                'status': 'active',
                'targetKey': '#asset#server01#server01',
                'clientId': 'C.1',
            }
        ]
        completer = ScheduleCompleter(schedules, agent_lookup={'C.1': 'server01'})

        class FakeDoc:
            text_before_cursor = 'abc'

        completions = list(completer.get_completions(FakeDoc(), None))
        assert len(completions) == 1
        assert completions[0].text == 'abc123-def456'

    def test_no_completions_for_non_matching(self):
        schedules = [
            {
                'scheduleId': 'abc123',
                'capabilityName': 'windows-smb',
                'status': 'active',
                'targetKey': '',
                'clientId': '',
            }
        ]
        completer = ScheduleCompleter(schedules)

        class FakeDoc:
            text_before_cursor = 'zzz'

        completions = list(completer.get_completions(FakeDoc(), None))
        assert len(completions) == 0

    def test_empty_input_returns_all(self):
        schedules = [
            {'scheduleId': 'aaa', 'capabilityName': 'cap1', 'status': 'active', 'targetKey': '', 'clientId': ''},
            {'scheduleId': 'bbb', 'capabilityName': 'cap2', 'status': 'paused', 'targetKey': '', 'clientId': ''},
        ]
        completer = ScheduleCompleter(schedules)

        class FakeDoc:
            text_before_cursor = ''

        completions = list(completer.get_completions(FakeDoc(), None))
        assert len(completions) == 2


# --- find_schedule_by_prefix tests ---

class MockSchedules:
    def __init__(self, schedules=None):
        self._schedules = schedules or []

    def list(self, pages=1):
        return self._schedules, None


class TestFindScheduleByPrefix:
    def test_finds_by_prefix(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([
            {'scheduleId': 'abc123-def456', 'capabilityName': 'test'},
            {'scheduleId': 'xyz789', 'capabilityName': 'other'},
        ])})()

        schedule, full_id = find_schedule_by_prefix(menu, 'abc')
        assert full_id == 'abc123-def456'
        assert schedule['capabilityName'] == 'test'

    def test_returns_none_when_not_found(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([
            {'scheduleId': 'abc123', 'capabilityName': 'test'},
        ])})()

        schedule, full_id = find_schedule_by_prefix(menu, 'zzz')
        assert schedule is None
        assert full_id is None

    def test_returns_none_on_empty_list(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([])})()

        schedule, full_id = find_schedule_by_prefix(menu, 'abc')
        assert schedule is None
        assert full_id is None

    def test_returns_none_on_api_error(self):
        class BrokenSchedules:
            def list(self, pages=1):
                raise Exception("API error")

        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': BrokenSchedules()})()

        schedule, full_id = find_schedule_by_prefix(menu, 'abc')
        assert schedule is None
        assert full_id is None


# --- complete_schedule_ids tests ---

class TestCompleteScheduleIds:
    def test_matches_by_id_prefix(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([
            {'scheduleId': 'abc123-def456', 'capabilityName': 'test', 'clientId': ''},
        ])})()

        results = complete_schedule_ids(menu, 'abc')
        assert len(results) == 1
        assert results[0] == 'abc123-def'  # Short ID (first 10 chars)

    def test_matches_by_capability_name(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([
            {'scheduleId': 'abc123-def456', 'capabilityName': 'windows-smb', 'clientId': ''},
        ])})()

        results = complete_schedule_ids(menu, 'windows')
        assert len(results) == 1

    def test_no_matches_returns_empty(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([
            {'scheduleId': 'abc123', 'capabilityName': 'test', 'clientId': ''},
        ])})()

        results = complete_schedule_ids(menu, 'zzz')
        assert len(results) == 0

    def test_empty_schedules_returns_empty(self):
        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': MockSchedules([])})()

        results = complete_schedule_ids(menu, '')
        assert len(results) == 0

    def test_api_error_returns_empty(self):
        class BrokenSchedules:
            def list(self, pages=1):
                raise Exception("API error")

        menu = MockMenuBase()
        menu.sdk = type('SDK', (), {'schedules': BrokenSchedules()})()

        results = complete_schedule_ids(menu, 'abc')
        assert len(results) == 0
