import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestAttribute:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        self.sdk.assets.add(self.asset_dns, self.asset_name)

    def test_add_attribute(self):
        a = self.sdk.attributes.add(self.asset_key, self.attribute_name, self.attribute_value)
        assert a['key'] == self.asset_attribute_key

    def test_list_attributes(self):
        results, _ = self.sdk.attributes.list()
        assert len(results) > 0
        assert any([r['name'] == self.attribute_name for r in results])

    def test_get_attribute(self):
        a = self.sdk.attributes.get(self.asset_attribute_key)
        assert a['name'] == self.attribute_name
        assert a['value'] == self.attribute_value
        assert a['source'] == self.asset_key

    def test_delete_attribute(self):
        self.sdk.attributes.delete(self.asset_attribute_key)
        assert self.sdk.attributes.get(self.asset_attribute_key) == None

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
