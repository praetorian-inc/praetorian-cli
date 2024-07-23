import time

import pytest

from praetorian_cli.handlers.utils import Asset
from praetorian_cli.sdk.test import BaseTest
from praetorian_cli.sdk.test.utils import Utils


@pytest.fixture(scope="class", params=[f"contoso-{int(time.time())}.com", "10.1.1.1/32"])
def asset(request):
    request.cls.asset = request.param


@pytest.mark.usefixtures("asset")
@pytest.mark.coherence
class TestAsset(BaseTest):

    def setup_class(self):
        self.chariot, self.username = BaseTest.setup_chariot(self)
        self.utils = Utils(self.chariot)

    def test_add_asset(self):
        response = self.chariot.add('asset', dict(dns=self.asset, name=self.asset))[0]
        assert response['dns'] == self.asset, "Response does not have correct asset"
        assert response['status'] == Asset.ACTIVE.value, "Response does not have correct status"

    def test_my_asset(self):
        response = self.chariot.my(dict(key=f'#asset#'))
        assert any(
            my_asset['dns'] == self.asset for my_asset in response['assets']), "None of the assets matched self.asset"

    def test_my_job(self):
        response = self.chariot.my(dict(key=f'#job#{self.asset}'))
        assert response is not None, "Received empty response for my Jobs"
        for job in response['jobs']:
            assert job['source'] is not '', "Job Capability is empty"
            assert job['status'] is not None, "Job Status is empty"

    def test_freeze_asset(self):
        response = self.chariot.update('asset', dict(key=f'#asset#{self.asset}', status=Asset.FROZEN.value))[0]
        assert response['status'] == Asset.FROZEN.value, "Response does not have correct status"

    def test_delete_asset(self):
        self.chariot.update('asset', dict(key=f'#asset#{self.asset}', status='D'))
        response = self.chariot.my(dict(key=f'#asset#{self.asset}'))
        assert response['assets'][0]['status'] == 'D'
