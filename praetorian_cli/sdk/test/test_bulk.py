import json
import pytest
from unittest.mock import MagicMock, patch

from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.sdk.entities.risks import Risks
from praetorian_cli.sdk.entities.attributes import Attributes
from praetorian_cli.sdk.entities.jobs import Jobs


class TestAssetsBulkAdd:

    def setup_method(self):
        self.api = MagicMock()
        self.assets = Assets(self.api)

    def test_bulk_add_minimal(self):
        """bulk_add with only required fields uses correct defaults."""
        items = [dict(group='example.com', identifier='1.2.3.4')]
        self.api.post.return_value = {'job': 'j1'}

        result = self.assets.bulk_add(items)

        self.api.post.assert_called_once_with('bulk/asset', dict(
            action='upsert',
            items=[dict(
                group='example.com',
                identifier='1.2.3.4',
                status=Asset.ACTIVE.value,
                attackSurface=[''],
                type=Kind.ASSET.value,
            )]
        ))
        assert result == {'job': 'j1'}

    def test_bulk_add_with_all_optional_fields(self):
        """bulk_add passes through all optional fields correctly."""
        items = [dict(
            group='example.com',
            identifier='1.2.3.4',
            type=Kind.ADDOMAIN.value,
            status=Asset.FROZEN.value,
            surface='internal',
            resource_type='AWS::EC2::Instance',
        )]
        self.api.post.return_value = {'job': 'j1'}

        self.assets.bulk_add(items)

        call_args = self.api.post.call_args
        payload_items = call_args[0][1]['items']
        assert len(payload_items) == 1
        item = payload_items[0]
        assert item['group'] == 'example.com'
        assert item['identifier'] == '1.2.3.4'
        assert item['type'] == Kind.ADDOMAIN.value
        assert item['status'] == Asset.FROZEN.value
        assert item['attackSurface'] == ['internal']
        assert item['resourceType'] == 'AWS::EC2::Instance'

    def test_bulk_add_multiple_items(self):
        """bulk_add handles multiple items in a single call."""
        items = [
            dict(group='a.com', identifier='1.1.1.1'),
            dict(group='b.com', identifier='2.2.2.2'),
        ]
        self.api.post.return_value = {'job': 'j1'}

        self.assets.bulk_add(items)

        call_args = self.api.post.call_args
        payload_items = call_args[0][1]['items']
        assert len(payload_items) == 2

    def test_bulk_add_without_resource_type_omits_key(self):
        """When resource_type is not provided, resourceType key is absent from payload."""
        items = [dict(group='example.com', identifier='1.2.3.4')]
        self.api.post.return_value = {'job': 'j1'}

        self.assets.bulk_add(items)

        call_args = self.api.post.call_args
        item = call_args[0][1]['items'][0]
        assert 'resourceType' not in item


class TestRisksBulkAdd:

    def setup_method(self):
        self.api = MagicMock()
        self.risks = Risks(self.api)

    def test_bulk_add_minimal(self):
        """bulk_add with only required fields."""
        items = [dict(asset_key='#asset#a.com#1.1.1.1', name='vuln-1', status='TH')]
        self.api.post.return_value = {'job': 'j1'}

        result = self.risks.bulk_add(items)

        self.api.post.assert_called_once_with('bulk/risk', dict(
            action='upsert',
            items=[dict(key='#asset#a.com#1.1.1.1', name='vuln-1', status='TH')]
        ))
        assert result == {'job': 'j1'}

    def test_bulk_add_with_all_optional_fields(self):
        """bulk_add passes through comment, capability, title, tags."""
        items = [dict(
            asset_key='#asset#a.com#1.1.1.1',
            name='vuln-1',
            status='TH',
            comment='found during scan',
            capability='nuclei',
            title='SQL Injection',
            tags=['critical', 'web'],
        )]
        self.api.post.return_value = {'job': 'j1'}

        self.risks.bulk_add(items)

        call_args = self.api.post.call_args
        item = call_args[0][1]['items'][0]
        assert item['comment'] == 'found during scan'
        assert item['source'] == 'nuclei'
        assert item['title'] == 'SQL Injection'
        assert item['tags'] == ['critical', 'web']

    def test_bulk_add_omits_absent_optional_fields(self):
        """When optional fields are not provided, their keys are absent."""
        items = [dict(asset_key='#asset#a.com#1.1.1.1', name='vuln-1', status='TH')]
        self.api.post.return_value = {'job': 'j1'}

        self.risks.bulk_add(items)

        call_args = self.api.post.call_args
        item = call_args[0][1]['items'][0]
        assert 'comment' not in item
        assert 'source' not in item
        assert 'title' not in item
        assert 'tags' not in item

    def test_bulk_add_tags_converted_to_list(self):
        """Tags tuple is converted to a list."""
        items = [dict(
            asset_key='#asset#a.com#1.1.1.1',
            name='vuln-1',
            status='TH',
            tags=('a', 'b'),
        )]
        self.api.post.return_value = {'job': 'j1'}

        self.risks.bulk_add(items)

        call_args = self.api.post.call_args
        item = call_args[0][1]['items'][0]
        assert item['tags'] == ['a', 'b']
        assert isinstance(item['tags'], list)


class TestAttributesBulkAdd:

    def setup_method(self):
        self.api = MagicMock()
        self.attributes = Attributes(self.api)

    def test_bulk_add(self):
        """bulk_add constructs the correct payload."""
        items = [
            dict(source_key='#asset#a.com#1.1.1.1', name='port', value='443'),
            dict(source_key='#asset#b.com#2.2.2.2', name='proto', value='https'),
        ]
        self.api.post.return_value = {'job': 'j1'}

        result = self.attributes.bulk_add(items)

        self.api.post.assert_called_once_with('bulk/attribute', dict(
            action='upsert',
            items=[
                dict(key='#asset#a.com#1.1.1.1', name='port', value='443'),
                dict(key='#asset#b.com#2.2.2.2', name='proto', value='https'),
            ]
        ))
        assert result == {'job': 'j1'}


class TestJobsBulkResults:

    def setup_method(self):
        self.api = MagicMock()
        self.jobs = Jobs(self.api)

    def test_bulk_results_passed_job(self):
        """bulk_results downloads and parses results for a passed job."""
        job = {
            'status': 'JP',
            'config': {'results_s3_key': 'results/bulk-123.json'},
        }
        expected = {'summary': {'total': 1}, 'results': [{'key': '#asset#a.com#1.1.1.1'}]}
        self.api.files.get_utf8.return_value = json.dumps(expected)

        result = self.jobs.bulk_results(job)

        self.api.files.get_utf8.assert_called_once_with('results/bulk-123.json')
        assert result == expected

    def test_bulk_results_failed_job(self):
        """bulk_results works for failed jobs too (they can have results)."""
        job = {
            'status': 'JF',
            'config': {'results_s3_key': 'results/bulk-456.json'},
        }
        expected = {'summary': {'total': 0, 'errors': 1}, 'results': []}
        self.api.files.get_utf8.return_value = json.dumps(expected)

        result = self.jobs.bulk_results(job)

        assert result == expected

    def test_bulk_results_incomplete_job_returns_none(self):
        """bulk_results returns None for jobs that are still running."""
        job = {'status': 'JR', 'config': {'results_s3_key': 'results/bulk-789.json'}}

        result = self.jobs.bulk_results(job)

        assert result is None
        self.api.files.get_utf8.assert_not_called()

    def test_bulk_results_no_results_key_returns_none(self):
        """bulk_results returns None when config has no results_s3_key."""
        job = {'status': 'JP', 'config': {}}

        result = self.jobs.bulk_results(job)

        assert result is None

    def test_bulk_results_no_config_returns_none(self):
        """bulk_results returns None when job has no config."""
        job = {'status': 'JP'}

        result = self.jobs.bulk_results(job)

        assert result is None


class TestJobsWait:

    def setup_method(self):
        self.api = MagicMock()
        self.jobs = Jobs(self.api)

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_returns_on_passed(self, mock_time, mock_sleep):
        """wait returns immediately when job is passed."""
        mock_time.side_effect = [0, 1]  # start, first check
        completed_job = {'status': 'JP', 'key': '#job#test'}
        self.api.search.by_exact_key.return_value = completed_job

        result = self.jobs.wait('#job#test')

        assert result == completed_job
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_returns_on_failed(self, mock_time, mock_sleep):
        """wait returns when job transitions to failed."""
        mock_time.side_effect = [0, 1]
        failed_job = {'status': 'JF', 'key': '#job#test'}
        self.api.search.by_exact_key.return_value = failed_job

        result = self.jobs.wait('#job#test')

        assert result == failed_job

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_polls_until_complete(self, mock_time, mock_sleep):
        """wait polls multiple times until job completes."""
        mock_time.side_effect = [0, 1, 6, 11]
        running_job = {'status': 'JR', 'key': '#job#test'}
        passed_job = {'status': 'JP', 'key': '#job#test'}
        self.api.search.by_exact_key.side_effect = [running_job, running_job, passed_job]

        result = self.jobs.wait('#job#test', poll_interval=5)

        assert result == passed_job
        assert self.api.search.by_exact_key.call_count == 3
        assert mock_sleep.call_count == 2

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_timeout(self, mock_time, mock_sleep):
        """wait raises TimeoutError when timeout is exceeded."""
        # First call is start time=0, subsequent calls exceed timeout
        mock_time.side_effect = [0, 1, 100, 200]
        running_job = {'status': 'JR', 'key': '#job#test'}
        self.api.search.by_exact_key.return_value = running_job

        with pytest.raises(TimeoutError, match='did not complete within 10s'):
            self.jobs.wait('#job#test', poll_interval=1, timeout=10)

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_handles_none_result(self, mock_time, mock_sleep):
        """wait continues polling when by_exact_key returns None."""
        mock_time.side_effect = [0, 1, 6, 11]
        passed_job = {'status': 'JP', 'key': '#job#test'}
        self.api.search.by_exact_key.side_effect = [None, None, passed_job]

        result = self.jobs.wait('#job#test', poll_interval=5)

        assert result == passed_job
        assert self.api.search.by_exact_key.call_count == 3
