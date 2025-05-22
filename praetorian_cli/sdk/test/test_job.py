import pytest
import json

from praetorian_cli.sdk.model.utils import asset_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestJob:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

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

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
