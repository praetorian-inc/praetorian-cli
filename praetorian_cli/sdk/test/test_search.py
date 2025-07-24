import pytest

from praetorian_cli.sdk.model.globals import Asset, Kind, Risk
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestSearch:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        self.sdk.assets.add(self.asset_dns, self.asset_name)
        self.sdk.risks.add(self.asset_key, self.risk_name, Risk.TRIAGE_HIGH.value, self.comment)
        self.sdk.attributes.add(self.asset_key, self.attribute_name, self.attribute_value)


    def test_search_by_key_prefix(self):
        hits, _ = self.sdk.search.by_key_prefix(f'#asset#{self.asset_dns}#')
        assert len(hits) == 1
        assert hits[0]['key'] == self.asset_key

    def test_search_by_exact_key(self):
        assert self.sdk.search.by_exact_key(f'#asset#{self.asset_dns}#') == None
        assert self.sdk.search.by_exact_key(self.asset_key)['key'] == self.asset_key

    def test_search_as_global_user(self):
        assert len(self.sdk.search.by_term(self.asset_key, exact=True, global_=True)[0]) == 0

    def test_search_by_source(self):
        hits, _ = self.sdk.search.by_source(self.asset_key, Kind.ATTRIBUTE.value)
        assert len(hits) > 0
        assert any([h['key'] == self.asset_attribute_key for h in hits])

    def test_search_by_status(self):
        hits, _ = self.sdk.search.by_status(Asset.ACTIVE.value, Kind.ASSET.value)
        assert len(hits) >= 1
        assert any([h['group'] == self.asset_dns for h in hits])

    def test_search_by_dns(self):
        hits, _ = self.sdk.search.by_dns(self.asset_dns, Kind.ASSET.value)
        assert len(hits) == 1
        assert hits[0]['group'] == self.asset_dns

    def test_search_by_name(self):
        hits, _ = self.sdk.search.by_name(self.asset_name, Kind.ASSET.value)
        assert len(hits) == 1
        assert hits[0]['group'] == self.asset_dns

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
