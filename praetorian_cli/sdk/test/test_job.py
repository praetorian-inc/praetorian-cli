import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestJob:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_job(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_name)
        asset_key = result['key']
        self.sdk.jobs.add(asset_key)
        jobs, _ = self.sdk.jobs.list(self.asset_dns)
        assert len(jobs) > 0
        assert jobs[0]['dns'] == self.asset_dns

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
