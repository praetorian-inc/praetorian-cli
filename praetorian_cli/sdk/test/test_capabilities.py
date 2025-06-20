import pytest

from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestCapabilities:

    def setup_class(self):
        self.sdk = setup_chariot()

    def test_list_capabilities(self):
        capabilities = self.sdk.capabilities.list()
        assert len(capabilities) > 0
