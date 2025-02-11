import pytest

from praetorian_cli.sdk.model.globals import Risk
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestRisk:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_attribution(self):
        result = self.sdk.assets.add(self.asset_dns, self.asset_name)
        assert result['key'] == self.asset_key
        result = self.sdk.risks.add(self.asset_key, self.risk_name, Risk.TRIAGE_HIGH.value, self.comment)
        assert result['key'] == self.risk_key

        # the following at least tests the affiliation code compiles
        with pytest.raises(Exception) as ex_info:
            self.sdk.agents.affiliation(self.risk_key, 1)
        assert str(ex_info.value) == 'Timeout waiting for affiliation result (1 seconds).'

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
