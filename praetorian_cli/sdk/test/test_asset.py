import pytest

from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestAsset:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_asset(self):
        asset = self.sdk.assets.add(self.asset_dns, self.asset_name, Asset.ACTIVE.value, 'test-surface')
        print(asset)
        assert asset['key'] == self.asset_key
        assert len(asset['surface']) == 1
        assert asset['surface'][0] == 'test-surface'
        assert asset['status'] == Asset.ACTIVE.value

    def test_get_asset(self):
        a = self.get_asset()
        assert a['dns'] == self.asset_dns
        assert a['name'] == self.asset_name
        assert a['status'] == Asset.ACTIVE.value

    def test_list_asset(self):
        results, _ = self.sdk.assets.list()
        assert len(results) > 0
        assert any([a['dns'] == self.asset_dns for a in results])

    def test_update_asset(self):
        self.sdk.assets.update(self.asset_key, status=Asset.FROZEN.value)
        assert self.get_asset()['status'] == Asset.FROZEN.value
        self.sdk.assets.update(self.asset_key, surface='abc')
        attributes = self.sdk.assets.attributes(self.asset_key)
        assert any([a['name'] == 'surface' and a['value'] == 'abc' for a in attributes])

    def test_delete_asset(self):
        self.sdk.assets.delete(self.asset_key)
        assert self.get_asset()['status'] == Asset.DELETED.value
        deleted_assets, _ = self.sdk.search.by_status(Asset.DELETED.value, Kind.ASSET.value)
        assert any([a['dns'] == self.asset_dns for a in deleted_assets])

    def get_asset(self):
        return self.sdk.assets.get(self.asset_key)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
