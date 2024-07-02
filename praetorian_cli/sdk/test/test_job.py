import time

import pytest

from praetorian_cli.sdk.test import BaseTest, utils


@pytest.mark.coherence
class TestJob(BaseTest):
    test_id = int(time.time())
    asset_payload = dict(dns=f"contoso-{test_id}.com", name="10.1.1.5")
    job_payload = dict(name=f"portscan")

    def setup_class(self):
        self.chariot, self.username = BaseTest.setup_chariot(self)
        webhook = self.chariot.add_webhook()
        utils.add_asset_via_webhook(webhook, self.asset_payload)

    def test_add_job(self):
        response = self.chariot.my(dict(key=f'#asset#{TestJob.asset_payload["dns"]}'))
        assert response['assets'], "No assets found"
        TestJob.job_payload['key'] = response['assets'][0]['key']
        response = self.chariot.add('job', TestJob.job_payload)
        for job in response:
            assert job['source'] == TestJob.job_payload['name']

    def test_my_job(self):
        response = self.chariot.my(dict(key=f'#job#{TestJob.asset_payload["dns"]}'))
        assert any(my_job['source'] == TestJob.job_payload['name'] for my_job in response['jobs']), \
            "None of the jobs matched self.job_payload['name']"
