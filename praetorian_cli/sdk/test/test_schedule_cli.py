import json
import pytest
from unittest.mock import MagicMock, patch, call
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.schedule import _parse_weekly_schedule


def _invoke(runner, sdk, argv, **kwargs):
    """Invoke the CLI with a patched SDK factory.

    The `chariot` click group replaces `ctx.obj` with a `Chariot` instance,
    built lazily inside the group callback via `from praetorian_cli.sdk.chariot
    import Chariot`. We patch that source symbol so every instantiation yields
    our fake SDK. We also seed `ctx.obj` with the dict shape the group expects
    (`{'keychain', 'proxy'}`) so invocation doesn't blow up before the patch
    takes effect. (Mirrors the pattern used in test_export_cli.py / test_run_cli.py.)
    """
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, **kwargs)


class TestParseWeeklySchedule:

    def test_single_day(self):
        result = _parse_weekly_schedule('monday', '10:00')
        assert result['monday'] == {'enabled': True, 'time': '10:00'}
        assert result['tuesday'] == {'enabled': False, 'time': ''}

    def test_multiple_days(self):
        result = _parse_weekly_schedule('monday,wednesday,friday', '14:00')
        assert result['monday']['enabled'] is True
        assert result['wednesday']['enabled'] is True
        assert result['friday']['enabled'] is True
        assert result['tuesday']['enabled'] is False

    def test_all_days(self):
        result = _parse_weekly_schedule(
            'monday,tuesday,wednesday,thursday,friday,saturday,sunday', '09:00')
        for day in result.values():
            assert day['enabled'] is True
            assert day['time'] == '09:00'

    def test_invalid_day_calls_error(self):
        with pytest.raises(SystemExit):
            _parse_weekly_schedule('monday,badday', '10:00')


class TestScheduleCreate:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()
        self.sdk.schedules.create.return_value = {'scheduleId': 'sched-1'}

    def test_create_basic(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'create',
            '--capability', 'nuclei',
            '--target', '#asset#example.com#example.com',
            '--days', 'monday,friday',
            '--time', '10:00',
            '--start-date', '2024-01-15T00:00:00Z',
        ])
        assert result.exit_code == 0
        self.sdk.schedules.create.assert_called_once()
        call_kwargs = self.sdk.schedules.create.call_args[1]
        assert call_kwargs['capability_name'] == 'nuclei'
        assert call_kwargs['target_key'] == '#asset#example.com#example.com'
        assert call_kwargs['weekly_schedule']['monday']['enabled'] is True
        assert call_kwargs['weekly_schedule']['friday']['enabled'] is True
        assert call_kwargs['weekly_schedule']['tuesday']['enabled'] is False
        assert call_kwargs['start_date'] == '2024-01-15T00:00:00Z'
        assert call_kwargs['end_date'] is None
        assert call_kwargs['config'] is None

    def test_create_with_all_options(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'create',
            '--capability', 'portscan',
            '--target', '#asset#10.0.0.1#10.0.0.1',
            '--days', 'monday',
            '--time', '02:00',
            '--start-date', '2024-01-01T00:00:00Z',
            '--end-date', '2024-12-31T23:59:59Z',
            '--config', '{"templates":"cves/"}',
            '--client-id', 'aegis-client-1',
        ])
        assert result.exit_code == 0
        call_kwargs = self.sdk.schedules.create.call_args[1]
        assert call_kwargs['end_date'] == '2024-12-31T23:59:59Z'
        assert call_kwargs['config'] == {'templates': 'cves/'}
        assert call_kwargs['client_id'] == 'aegis-client-1'

    def test_create_invalid_config_json(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'create',
            '--capability', 'nuclei',
            '--target', '#asset#x#x',
            '--days', 'monday',
            '--time', '10:00',
            '--start-date', '2024-01-01T00:00:00Z',
            '--config', 'not-json',
        ])
        assert result.exit_code != 0


class TestScheduleUpdate:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()
        self.sdk.schedules.update.return_value = {'scheduleId': 'sched-1', 'status': 'active'}

    def test_update_days_and_time(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'update', 'sched-1',
            '--days', 'monday,tuesday',
            '--time', '14:00',
        ])
        assert result.exit_code == 0
        call_kwargs = self.sdk.schedules.update.call_args[1]
        assert call_kwargs['schedule_id'] == 'sched-1'
        assert call_kwargs['weekly_schedule']['monday']['enabled'] is True
        assert call_kwargs['weekly_schedule']['tuesday']['enabled'] is True

    def test_update_end_date_only(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'update', 'sched-1',
            '--end-date', '2025-06-30T23:59:59Z',
        ])
        assert result.exit_code == 0
        call_kwargs = self.sdk.schedules.update.call_args[1]
        assert call_kwargs['end_date'] == '2025-06-30T23:59:59Z'
        assert call_kwargs['weekly_schedule'] is None

    def test_update_days_without_time_fails(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'update', 'sched-1',
            '--days', 'monday',
        ])
        assert result.exit_code != 0

    def test_update_sdk_error(self):
        self.sdk.schedules.update.side_effect = Exception('Not found')
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'update', 'sched-1',
            '--start-date', '2025-01-01T00:00:00Z',
        ])
        assert result.exit_code != 0


class TestScheduleDelete:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_delete_with_force(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'delete', 'sched-1', '--force',
        ])
        assert result.exit_code == 0
        self.sdk.schedules.delete.assert_called_once_with('sched-1')
        assert 'deleted' in result.output.lower()

    def test_delete_with_confirmation(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'delete', 'sched-1',
        ], input='y\n')
        assert result.exit_code == 0
        self.sdk.schedules.delete.assert_called_once_with('sched-1')

    def test_delete_cancelled(self):
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'delete', 'sched-1',
        ], input='n\n')
        assert result.exit_code == 0
        self.sdk.schedules.delete.assert_not_called()
        assert 'cancelled' in result.output.lower()

    def test_delete_sdk_error(self):
        self.sdk.schedules.delete.side_effect = Exception('Backend error')
        result = _invoke(self.runner, self.sdk, [
            'schedule', 'delete', 'sched-1', '--force',
        ])
        assert result.exit_code != 0
