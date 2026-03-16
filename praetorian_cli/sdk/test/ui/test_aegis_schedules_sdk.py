"""Tests for SDK schedules entity - verifies routing through self.api helpers."""

import pytest
from unittest.mock import MagicMock
from praetorian_cli.sdk.entities.schedules import Schedules

pytestmark = pytest.mark.tui


class TestCreate:
    """Test that create() builds the correct body and routes through self.api.post."""

    def _make_schedules(self):
        api = MagicMock()
        api.post.return_value = {'scheduleId': 'fff0-aaa1', 'status': 'active'}
        return Schedules(api), api

    def test_create_minimal_body(self):
        sched, api = self._make_schedules()
        weekly = {'monday': {'enabled': True, 'time': '10:00'}}

        sched.create(
            capability_name='windows-smb',
            target_key='#asset#host#host',
            weekly_schedule=weekly,
            start_date='2024-01-15T00:00:00Z',
        )

        api.post.assert_called_once()
        call_args = api.post.call_args
        assert call_args[0][0] == 'capability/schedule'
        body = call_args[0][1]
        assert body['capabilityName'] == 'windows-smb'
        assert body['targetKey'] == '#asset#host#host'
        assert body['weeklySchedule'] == weekly
        assert body['startDate'] == '2024-01-15T00:00:00Z'
        assert 'endDate' not in body
        assert 'config' not in body
        assert 'clientId' not in body

    def test_create_with_all_optional_fields(self):
        sched, api = self._make_schedules()
        weekly = {'monday': {'enabled': True, 'time': '10:00'}}

        sched.create(
            capability_name='ad-enum',
            target_key='#addomain#example.local#example.local',
            weekly_schedule=weekly,
            start_date='2024-01-15T00:00:00Z',
            end_date='2024-12-31T23:59:59Z',
            config={'aegis': 'true', 'credential_id': 'cred-123'},
            client_id='C.abc123',
        )

        body = api.post.call_args[0][1]
        assert body['endDate'] == '2024-12-31T23:59:59Z'
        assert body['config']['credential_id'] == 'cred-123'
        assert body['clientId'] == 'C.abc123'

    def test_create_returns_api_response(self):
        sched, api = self._make_schedules()
        weekly = {'monday': {'enabled': True, 'time': '10:00'}}

        result = sched.create(
            capability_name='test',
            target_key='#asset#h#h',
            weekly_schedule=weekly,
            start_date='2024-01-15T00:00:00Z',
        )
        assert result['scheduleId'] == 'fff0-aaa1'


class TestUpdate:
    """Test that update() builds the correct body and routes through self.api.put."""

    def _make_schedules(self):
        api = MagicMock()
        api.put.return_value = {'scheduleId': 'aaa0-bbb1', 'status': 'active'}
        return Schedules(api), api

    def test_update_only_weekly_schedule(self):
        sched, api = self._make_schedules()
        weekly = {'tuesday': {'enabled': True, 'time': '14:00'}}

        sched.update(schedule_id='aaa0-bbb1', weekly_schedule=weekly)

        api.put.assert_called_once()
        assert api.put.call_args[0][0] == 'capability/schedule/aaa0-bbb1'
        body = api.put.call_args[0][1]
        assert body['weeklySchedule'] == weekly
        assert 'startDate' not in body
        assert 'endDate' not in body

    def test_update_no_fields_sends_empty_body(self):
        sched, api = self._make_schedules()

        sched.update(schedule_id='aaa0-bbb1')

        body = api.put.call_args[0][1]
        assert body == {}


class TestDelete:
    """Test delete routes through self.api.delete."""

    def test_delete_calls_api_delete(self):
        api = MagicMock()
        api.delete.return_value = {}
        sched = Schedules(api)

        sched.delete('ddd0-eee1')

        api.delete.assert_called_once_with('capability/schedule/ddd0-eee1', {}, {})


class TestPause:
    """Test pause routes through self.api.patch."""

    def test_pause_calls_api_patch(self):
        api = MagicMock()
        api.patch.return_value = {'scheduleId': 'ccc0-ddd1', 'status': 'paused'}
        sched = Schedules(api)

        result = sched.pause('ccc0-ddd1')

        api.patch.assert_called_once_with('capability/schedule/ccc0-ddd1/pause')
        assert result['status'] == 'paused'


class TestResume:
    """Test resume routes through self.api.patch."""

    def test_resume_calls_api_patch(self):
        api = MagicMock()
        api.patch.return_value = {'scheduleId': 'ccc0-ddd1', 'status': 'active'}
        sched = Schedules(api)

        result = sched.resume('ccc0-ddd1')

        api.patch.assert_called_once_with('capability/schedule/ccc0-ddd1/resume')
        assert result['status'] == 'active'


class TestList:
    """Test list() queries with correct key prefix."""

    def test_list_returns_schedules(self):
        api = MagicMock()
        api.my.return_value = {
            'capabilityschedules': [
                {'scheduleId': 'a', 'status': 'active'},
                {'scheduleId': 'b', 'status': 'paused'},
            ],
            'offset': None,
        }
        sched = Schedules(api)

        schedules, offset = sched.list()

        assert len(schedules) == 2
        assert offset is None
        api.my.assert_called_once_with({'key': '#capability_schedule#'}, pages=1)

    def test_list_empty_returns_empty(self):
        api = MagicMock()
        api.my.return_value = {'capabilityschedules': [], 'offset': None}
        sched = Schedules(api)

        schedules, offset = sched.list()

        assert schedules == []


class TestGet:
    """Test get() passes correct key to search."""

    def test_get_builds_correct_key(self):
        api = MagicMock()
        api.search = MagicMock()
        api.search.by_exact_key.return_value = {'scheduleId': 'aaa0-bbb1'}
        sched = Schedules(api)

        result = sched.get('aaa0-bbb1')

        api.search.by_exact_key.assert_called_once_with('#capability_schedule#aaa0-bbb1')
        assert result['scheduleId'] == 'aaa0-bbb1'
