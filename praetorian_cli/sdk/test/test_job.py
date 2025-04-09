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

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
