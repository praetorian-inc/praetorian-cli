import pytest

from praetorian_cli.sdk.model.globals import Asset
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestSearch:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        self.sdk.assets.add(self.asset_dns, self.asset_name, Asset.ACTIVE.value)
        self.sdk.attributes.add(self.asset_key, self.attribute_name, self.attribute_value)

    def test_search_by_key_prefix(self):
        hits, _ = self.sdk.search.by_key_prefix(f'#asset#{self.asset_dns}#')
        assert len(hits) == 1
        assert hits[0]['key'] == self.asset_key

    def test_search_by_exact_key(self):
        assert self.sdk.search.by_exact_key(f'#asset#{self.asset_dns}#') is None
        assert self.sdk.search.by_exact_key(self.asset_key)['key'] == self.asset_key

    def test_search_by_source(self):
        hits, _ = self.sdk.search.by_source(self.asset_key)
        assert len(hits) > 1
        assert any(h['key'] == self.asset_attribute_key for h in hits)

    def test_search_by_status(self):
        hits, _ = self.sdk.search.by_status(Asset.ACTIVE.value)
        assert len(hits) > 1
        assert any(h['dns'] == self.asset_dns for h in hits)

    def test_search_by_dns(self):
        hits, _ = self.sdk.search.by_dns(self.asset_dns)
        assert len(hits) == 1
        assert hits[0]['dns'] == self.asset_dns

    def test_search_by_name(self):
        hits, _ = self.sdk.search.by_name(self.asset_name)
        assert len(hits) == 1
        assert hits[0]['dns'] == self.asset_dns

    def test_search_by_ip(self):
        hits, _ = self.sdk.search.by_ip(self.asset_name)
        assert len(hits) == 1
        assert hits[0]['dns'] == self.asset_dns

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
