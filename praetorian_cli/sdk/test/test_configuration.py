import pytest

from praetorian_cli.sdk.model.utils import configuration_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestConfigurations:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        if not self.sdk.is_praetorian_user():
            pytest.skip("This test is only available to Praetorian engineers")

    def test_add_configuration(self):
        self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        configurations, _ = self.sdk.configurations.list(self.configuration_name)
        assert len(configurations) > 0
        assert configurations[0]['name'] == self.configuration_name
        assert configurations[0]['value'] == self.configuration_value

    def test_get_configuration(self):
        self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        configuration = self.sdk.configurations.get(self.configuration_key)
        assert configuration is not None
        assert configuration['name'] == self.configuration_name
        assert configuration['value'] == self.configuration_value

    def test_delete_configuration(self):
        self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        self.sdk.configurations.delete(self.configuration_key)
        configurations, _ = self.sdk.configurations.list(self.configuration_name)
        assert len(configurations) == 0

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
