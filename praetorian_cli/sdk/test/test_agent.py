import pytest

from praetorian_cli.sdk.model.globals import Risk
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestRisk:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    @pytest.mark.skip(reason="This test is pending implementation on the ML side.")
    def test_attribution(self):
        # create the asset and risk to run attribution
        result = self.sdk.assets.add(self.asset_dns, self.asset_name)
        assert result['key'] == self.asset_key
        result = self.sdk.risks.add(self.asset_key, self.risk_name, Risk.TRIAGE_HIGH.value, self.comment)
        assert result['key'] == self.risk_key
        result = self.sdk.agents.attribution(self.risk_key)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
