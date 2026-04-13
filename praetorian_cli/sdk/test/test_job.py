import pytest
import json

from praetorian_cli.sdk.model.utils import asset_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestJob:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

        self.was_frozen = False
        frozen_setting = self.sdk.settings.get('#setting#frozen')
        if frozen_setting and frozen_setting.get('value') == 'true':
            self.was_frozen = True
            self.sdk.settings.add('frozen', 'false')

    def test_add_job(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        self.sdk.jobs.add(result['key'])
        jobs, _ = self.sdk.jobs.list(self.asset_dns)
        assert len(jobs) > 0
        assert jobs[0]['dns'] == self.asset_dns
        assert jobs[0]['key'].startswith('#job#')
        assert self.asset_dns in jobs[0]['key']

    def test_add_job_with_unknown_capability(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        with pytest.raises(Exception) as e:
            self.sdk.jobs.add(result['key'], ['unknown-not-a-capability'])
        assert 'unknown capability: unknown-not-a-capability' in str(e.value)
        
    def test_add_job_with_config(self):
        config = {"test_config_key": "test_config_value"}
        config_json = json.dumps(config)
        
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        jobs = self.sdk.jobs.add(result['key'], [], config_json)
        
        assert "config" in jobs[0]
        assert "test_config_key" in jobs[0]["config"]
        assert jobs[0]["config"]["test_config_key"] == "test_config_value"
            
    def test_add_job_with_invalid_config(self):
        invalid_json = '{"invalid_json": "missing_closing_brace"'
        
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        with pytest.raises(Exception) as e:
            self.sdk.jobs.add(result['key'], [], invalid_json)
        assert "Invalid JSON in configuration string" in str(e.value)

    def test_list_by_status(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        self.sdk.jobs.add(result['key'])

        jobs, _ = self.sdk.jobs.list_by_status('JQ')
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        for job in jobs:
            assert job['status'].startswith('JQ')

    def test_list_by_capability(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        self.sdk.jobs.add(result['key'], ['whois'])

        jobs, _ = self.sdk.jobs.list_by_capability('whois')
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        for job in jobs:
            assert job.get('source', '').startswith('whois')

    def test_list_by_target(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        self.sdk.jobs.add(result['key'])

        jobs, _ = self.sdk.jobs.list_by_target(self.asset_dns)
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        for job in jobs:
            assert self.asset_dns in job.get('dns', '') or self.asset_dns in job.get('key', '')

    def test_summary(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        self.sdk.jobs.add(result['key'])

        summary = self.sdk.jobs.summary()
        assert isinstance(summary, dict)
        assert 'total' in summary
        assert 'by_status' in summary
        assert 'by_capability' in summary
        assert summary['total'] > 0
        assert isinstance(summary['by_status'], dict)
        assert isinstance(summary['by_capability'], dict)
        assert len(summary['by_status']) > 0

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
        if self.was_frozen:
            self.sdk.settings.add('frozen', 'true')
