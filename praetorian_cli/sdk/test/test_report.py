from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.sdk.entities.reports import Reports


def make_reports(account=None, username=None):
    """Create a Reports instance with a mocked API."""
    api = MagicMock()
    api.keychain.account = account
    api.keychain.username.return_value = username
    return Reports(api), api


class TestCustomerEmail:

    def test_uses_account_when_set(self):
        reports, _ = make_reports(account='customer@acme.com', username='engineer@praetorian.com')
        assert reports.customer_email() == 'customer@acme.com'

    def test_falls_back_to_username(self):
        reports, _ = make_reports(account=None, username='engineer@praetorian.com')
        assert reports.customer_email() == 'engineer@praetorian.com'

    def test_raises_when_neither_set(self):
        reports, _ = make_reports(account=None, username=None)
        with pytest.raises(Exception, match='Could not determine customer email'):
            reports.customer_email()

    def test_prefers_account_over_username(self):
        reports, _ = make_reports(account='customer@acme.com', username='me@praetorian.com')
        assert reports.customer_email() == 'customer@acme.com'


class TestBuildExportBody:

    def test_minimal_body(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Test Report',
            client_name='Acme Corp',
            customer_email='customer@acme.com',
        )

        assert body['config']['title'] == 'Test Report'
        assert body['config']['client_name'] == 'Acme Corp'
        assert body['customer_email'] == 'customer@acme.com'
        assert body['status_filter'] == ['O', 'T']
        assert body['export_format'] == 'pdf'
        assert body['group_by'] == 'attack_surface'
        assert body['shared_output'] is False
        assert body['config']['draft'] is False
        assert body['config']['version'] == '1.0'
        assert 'risk_keys' not in body
        assert 'target' not in body['config']
        assert 'executive_summary_path' not in body

    def test_defaults_report_date_to_today(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Test', client_name='Test', customer_email='test@test.com',
        )
        assert body['config']['report_date'] == date.today().isoformat()

    def test_explicit_report_date(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Test', client_name='Test', customer_email='test@test.com',
            report_date='2026-01-15',
        )
        assert body['config']['report_date'] == '2026-01-15'

    def test_all_optional_fields(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Full Report',
            client_name='Acme',
            customer_email='customer@acme.com',
            status_filter=['O', 'T', 'R'],
            risk_keys=['#risk#example.com#sqli', '#risk#example.com#xss'],
            target='example.com',
            start_date='2026-01-01',
            end_date='2026-03-01',
            report_date='2026-03-15',
            draft=True,
            version='2.0',
            export_format='zip',
            group_by='tag',
            shared_output=True,
            executive_summary_path='home/exec-summary.md',
            narratives_path='home/narratives.md',
            appendix_path='home/appendix.md',
        )

        assert body['risk_keys'] == ['#risk#example.com#sqli', '#risk#example.com#xss']
        assert body['config']['target'] == 'example.com'
        assert body['config']['start_date'] == '2026-01-01'
        assert body['config']['end_date'] == '2026-03-01'
        assert body['config']['draft'] is True
        assert body['config']['version'] == '2.0'
        assert body['export_format'] == 'zip'
        assert body['group_by'] == 'tag'
        assert body['shared_output'] is True
        assert body['executive_summary_path'] == 'home/exec-summary.md'
        assert body['narratives_path'] == 'home/narratives.md'
        assert body['appendix_path'] == 'home/appendix.md'

    def test_status_filter_converts_tuple_to_list(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Test', client_name='Test', customer_email='test@test.com',
            status_filter=('O', 'T', 'R'),
        )
        assert body['status_filter'] == ['O', 'T', 'R']
        assert isinstance(body['status_filter'], list)

    def test_empty_optional_strings_excluded(self):
        reports, _ = make_reports()
        body = reports.build_export_body(
            title='Test', client_name='Test', customer_email='test@test.com',
            target='', executive_summary_path='', narratives_path='', appendix_path='',
        )
        assert 'target' not in body['config']
        assert 'executive_summary_path' not in body
        assert 'narratives_path' not in body
        assert 'appendix_path' not in body


class TestExport:

    def test_success(self):
        reports, api = make_reports()
        api.post.return_value = {'key': '#job#report#123'}
        api.jobs.get.return_value = {'status': 'JP', 'config': {'output': 'home/report.pdf'}}
        api.jobs.is_passed.return_value = True
        api.jobs.is_failed.return_value = False

        job = reports.export({'customer_email': 'test@test.com'}, timeout=10, poll_interval=0)

        api.post.assert_called_once_with('export/report', {'customer_email': 'test@test.com'})
        assert job['config']['output'] == 'home/report.pdf'

    def test_raises_on_missing_job_key(self):
        reports, api = make_reports()
        api.post.return_value = {}

        with pytest.raises(Exception, match='No job key returned'):
            reports.export({})

    def test_raises_on_failure(self):
        reports, api = make_reports()
        api.post.return_value = {'key': '#job#report#123'}
        api.jobs.get.return_value = {'status': 'JF', 'message': 'missing definitions'}
        api.jobs.is_failed.return_value = True
        api.jobs.is_passed.return_value = False

        with pytest.raises(Exception, match='Report generation failed: missing definitions'):
            reports.export({}, timeout=10, poll_interval=0)

    @patch('praetorian_cli.sdk.entities.reports.time')
    @patch('praetorian_cli.sdk.entities.reports.sleep')
    def test_raises_on_timeout(self, mock_sleep, mock_time):
        reports, api = make_reports()
        api.post.return_value = {'key': '#job#report#123'}
        api.jobs.get.return_value = {'status': 'JR'}
        api.jobs.is_failed.return_value = False
        api.jobs.is_passed.return_value = False

        # Simulate time progressing past timeout
        mock_time.side_effect = [0, 0, 100, 200, 301]

        with pytest.raises(Exception, match='timed out after 300 seconds'):
            reports.export({}, timeout=300, poll_interval=5)


class TestPollJob:

    @patch('praetorian_cli.sdk.entities.reports.sleep')
    def test_polls_until_passed(self, mock_sleep):
        reports, api = make_reports()

        # First call: running, second call: passed
        api.jobs.get.side_effect = [
            {'status': 'JR'},
            {'status': 'JP', 'config': {'output': 'home/report.pdf'}},
        ]
        api.jobs.is_failed.return_value = False
        api.jobs.is_passed.side_effect = [False, True]

        job = reports.poll_job('#job#123', timeout=60, poll_interval=0)
        assert job['status'] == 'JP'
        assert api.jobs.get.call_count == 2

    @patch('praetorian_cli.sdk.entities.reports.sleep')
    def test_raises_on_job_failure(self, mock_sleep):
        reports, api = make_reports()
        api.jobs.get.return_value = {'status': 'JF', 'message': 'orator crashed'}
        api.jobs.is_failed.return_value = True
        api.jobs.is_passed.return_value = False

        with pytest.raises(Exception, match='orator crashed'):
            reports.poll_job('#job#123', timeout=60, poll_interval=0)


class TestOutputPath:

    def test_from_config_output(self):
        reports, _ = make_reports()
        job = {'config': {'output': 'home/my-report-2026.pdf'}, 'dns': 'fallback.pdf'}
        assert reports.output_path(job) == 'home/my-report-2026.pdf'

    def test_falls_back_to_dns(self):
        reports, _ = make_reports()
        job = {'config': {}, 'dns': 'home/fallback.pdf'}
        assert reports.output_path(job) == 'home/fallback.pdf'

    def test_raises_when_no_path(self):
        reports, _ = make_reports()
        job = {'config': {}, 'dns': ''}
        with pytest.raises(Exception, match='Could not determine output file path'):
            reports.output_path(job)

    def test_raises_when_no_config(self):
        reports, _ = make_reports()
        job = {}
        with pytest.raises(Exception, match='Could not determine output file path'):
            reports.output_path(job)


class TestDownload:

    def test_delegates_to_files_save(self):
        reports, api = make_reports()
        api.files.save.return_value = '/tmp/my-report.pdf'

        job = {'config': {'output': 'home/my-report.pdf'}}
        result = reports.download(job, '/tmp')

        api.files.save.assert_called_once_with('home/my-report.pdf', '/tmp')
        assert result == '/tmp/my-report.pdf'
