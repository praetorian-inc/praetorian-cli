import pytest

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

    def test_add_job_with_unknown_capability(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
        with pytest.raises(Exception) as e:
            self.sdk.jobs.add(result['key'], ['unknown-not-a-capability'])
        assert 'unknown capability: unknown-not-a-capability' in str(e.value)
        
    def test_add_job_with_config_file(self):
        import json
        import os
        import tempfile
        
        config = {"test_config_key": "test_config_value"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
            json.dump(config, temp)
            temp_file_path = temp.name
        
        try:
            result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
            job_result = self.sdk.jobs.add(result['key'], [], temp_file_path)
            
            assert "test_config_key" in job_result
            assert job_result["test_config_key"] == "test_config_value"
        finally:
            os.unlink(temp_file_path)
            
    def test_add_job_with_invalid_config_file(self):
        import os
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
            temp.write('{"invalid_json": "missing_closing_brace"')
            temp_file_path = temp.name
        
        try:
            result = self.sdk.assets.add(self.asset_dns, self.asset_dns)
            with pytest.raises(Exception) as e:
                self.sdk.jobs.add(result['key'], [], temp_file_path)
            assert "Invalid JSON in configuration file" in str(e.value)
        finally:
            os.unlink(temp_file_path)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
