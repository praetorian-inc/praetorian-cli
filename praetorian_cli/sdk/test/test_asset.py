import time

import pytest

from praetorian_cli.handlers.utils import AssetPriorities
from praetorian_cli.sdk.asset import Asset
from praetorian_cli.sdk.job import Job
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
        self.asset_obj = Asset(self.chariot)

    def test_add_asset(self):
        a = self.asset_obj.add(self.asset, self.asset, 'standard')
        assert a['name'] == self.asset
        assert a['dns'] == self.asset
        assert a['status'] == AssetPriorities['standard']

    def test_details(self):
        a2 = Asset(self.chariot, self.asset_obj.details()['key'])
        a2_details = a2.details()
        assert a2_details['name'] == self.asset
        assert a2_details['dns'] == self.asset
        assert a2_details['status'] == AssetPriorities['standard']

    def test_add_attribute(self):
        a = self.asset_obj.add_attribute('test', 'test')
        for attr in a:
            assert attr['name'] == 'test'
            assert attr['value'] == 'test'
            assert attr['source'] == self.asset_obj.assetKey

    def test_attributes(self):
        a = self.asset_obj.attributes()
        assert len(a) > 0
        for attr in a:
            assert attr.details()['name'] is not ''
            assert attr.details()['value'] is not ''

    def test_my_job(self):
        job = Job(self.chariot).get(self.asset)
        assert job is not None
        for j in job:
            assert j['source'] is not ''
            assert j['status'] is not None
            assert j['dns'] == self.asset

    def test_freeze_asset(self):
        self.asset_obj.update('frozen')
        assert self.asset_obj.details()['status'] == AssetPriorities['frozen']

    def test_delete_asset(self):
        self.asset_obj.delete()
        with pytest.raises(Exception):
            self.asset_obj.details()
        assert self.asset_obj.assetKey is None
        assert self.asset_obj.assetDetails is None
