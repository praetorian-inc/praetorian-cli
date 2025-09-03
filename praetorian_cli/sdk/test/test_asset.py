import pytest

from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestAsset:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_asset(self):
        asset = self.sdk.assets.add(self.asset_dns, self.asset_name, status=Asset.ACTIVE.value, surface='test-surface')
        assert asset['key'] == self.asset_key
        assert len(asset['attackSurface']) == 1
        assert 'test-surface' in asset['attackSurface']
        assert asset['status'] == Asset.ACTIVE.value

    def test_get_asset(self):
        a = self.get_asset()
        assert a['group'] == self.asset_dns
        assert a['identifier'] == self.asset_name
        assert a['status'] == Asset.ACTIVE.value

    def test_list_asset(self):
        results, _ = self.sdk.assets.list()
        assert len(results) > 0
        assert any([a['group'] == self.asset_dns for a in results])

    def test_update_asset(self):
        self.sdk.assets.update(self.asset_key, status=Asset.FROZEN.value, surface='abc')
        asset = self.get_asset()
        assert asset['status'] == Asset.FROZEN.value
        assert 'abc' in asset['attackSurface']

    def test_delete_asset(self):
        self.sdk.assets.delete(self.asset_key)
        assert self.get_asset()['status'] == Asset.DELETED.value
        deleted_assets, _ = self.sdk.search.by_status(Asset.DELETED.value, Kind.ASSET.value)
        assert any([a['group'] == self.asset_dns for a in deleted_assets])
    
    def test_add_ad_domain(self):
        asset = self.sdk.assets.add(self.ad_domain_name, self.ad_object_id, status=Asset.ACTIVE.value, surface='test-surface', type=Kind.ADDOMAIN.value)
        assert asset['key'] == self.ad_domain_key
        assert len(asset['attackSurface']) == 1
        assert 'test-surface' in asset['attackSurface']
        assert asset['status'] == Asset.ACTIVE.value
    
    def test_get_ad_domain(self):
        asset = self.sdk.assets.get(self.ad_domain_key)
        assert asset['key'] == self.ad_domain_key
        assert asset['domain'] == self.ad_domain_name
        assert asset['status'] == Asset.ACTIVE.value
    
    def test_list_ad_domain(self):
        results, _ = self.sdk.assets.list(asset_type=Kind.ADDOMAIN.value)
        assert len(results) > 0
        assert any([a['group'] == self.ad_domain_name for a in results])
    
    def test_update_ad_domain(self):
        self.sdk.assets.update(self.ad_domain_key, status=Asset.FROZEN.value, surface='abc')
        ad_domain = self.get_ad_domain()
        assert ad_domain['status'] == Asset.FROZEN.value
        assert 'abc' in ad_domain['attackSurface']
    
    def test_delete_ad_domain(self):
        self.sdk.assets.delete(self.ad_domain_key)
        assert self.get_ad_domain()['status'] == Asset.DELETED.value
        deleted_assets, _ = self.sdk.search.by_status(Asset.DELETED.value, Kind.ADDOMAIN.value)
        assert any([a['key'] == self.ad_domain_key for a in deleted_assets])

    def get_asset(self):
        return self.sdk.assets.get(self.asset_key)
    
    def get_ad_domain(self):
        return self.sdk.assets.get(self.ad_domain_key)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
