import pytest

from praetorian_cli.sdk.model.globals import Risk, Kind
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestRisk:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_risk(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_name)
        asset_key = result['key']
        r = self.sdk.risks.add(asset_key, self.risk_name, Risk.TRIAGE_HIGH.value, self.comment)
        assert r['key'] == self.risk_key

    def test_get_risk(self):
        r = self.get_risk()
        assert r['name'] == self.risk_name
        assert r['status'] == Risk.TRIAGE_HIGH.value

    def test_list_risks(self):
        results, _ = self.sdk.risks.list()
        assert len(results) > 0
        assert any([r['dns'] == self.asset_dns for r in results])

    def test_bidirectional_links(self):
        affected_assets = self.sdk.risks.affected_assets(self.risk_key)
        assert len(affected_assets) == 1
        assert affected_assets[0]['key'] == self.asset_key
        associated_risks = self.sdk.assets.associated_risks(self.asset_key)
        assert len(associated_risks) == 1
        assert associated_risks[0]['key'] == self.risk_key

    def test_update_risk(self):
        self.sdk.risks.update(self.risk_key, Risk.OPEN_CRITICAL.value)
        assert self.get_risk()['status'] == Risk.OPEN_CRITICAL.value

    def test_delete_risk(self):
        self.sdk.risks.delete(self.risk_key, Risk.DELETED_DUPLICATE_CRITICAL.value)
        assert self.get_risk()['status'] == Risk.DELETED_DUPLICATE_CRITICAL.value
        deleted_risks, _ = self.sdk.search.by_status(Risk.DELETED_DUPLICATE_CRITICAL.value, Kind.RISK.value)
        assert any([r['name'] == self.risk_name for r in deleted_risks])

    def get_risk(self):
        return self.sdk.risks.get(self.risk_key)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
