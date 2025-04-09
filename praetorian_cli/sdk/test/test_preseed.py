import pytest

from praetorian_cli.sdk.model.globals import Preseed
from praetorian_cli.sdk.model.utils import asset_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestPreseed:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_preseed(self):
        self.sdk.preseeds.add(self.preseed_type, self.preseed_title, self.preseed_value, self.preseed_status)
        preseeds, _ = self.sdk.preseeds.list(self.preseed_type)
        assert len(preseeds) > 0
        assert preseeds[0]['type'] == self.preseed_type
        assert preseeds[0]['title'] == self.preseed_title
        assert preseeds[0]['value'] == self.preseed_value
        assert preseeds[0]['status'] == self.preseed_status

    def test_update_preseed(self):
        self.sdk.preseeds.update(self.preseed_key, Preseed.FROZEN_REJECTED.value)
        preseeds, _ = self.sdk.preseeds.list(self.preseed_type)
        assert len(preseeds) > 0
        assert preseeds[0]['status'] == Preseed.FROZEN_REJECTED.value

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
