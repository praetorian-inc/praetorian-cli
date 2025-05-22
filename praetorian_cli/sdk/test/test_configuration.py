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
        a = self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        assert a is not None
        assert a['name'] == self.configuration_name
        assert a['value'] == self.configuration_value

    def test_list_configurations(self):
        self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        results, _ = self.sdk.configurations.list()
        assert len(results) > 0
        assert any([r['name'] == self.configuration_name for r in results])

    def test_get_configuration(self):
        self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        configuration = self.sdk.configurations.get(self.configuration_key)
        assert configuration is not None
        assert configuration['name'] == self.configuration_name
        assert configuration['value'] == self.configuration_value

    def test_delete_configuration(self):
        a = self.sdk.configurations.add(self.configuration_name, self.configuration_value)
        print(a)
        self.sdk.configurations.delete(self.configuration_name)
        assert self.sdk.configurations.get(self.configuration_key) == None
        assert self.sdk.configurations.get(self.configuration_key) is None

    def test_delete_configuration_entry(self):
        test_dict = {"key1": "value1", "key2": "value2"}
        self.sdk.configurations.add(self.configuration_name, test_dict)

        from praetorian_cli.sdk.model.utils import configuration_key
        config_key = configuration_key(self.configuration_name)
        config = self.sdk.configurations.get(config_key)
        assert config is not None
        assert "key1" not in config['value']
        assert config['value']['key2'] == "value2"


    def teardown_class(self):
        clean_test_entities(self.sdk, self)
