import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestSettings:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_setting(self):
        s = self.sdk.settings.add(self.setting_name, self.setting_value)
        assert s is not None
        assert s['name'] == self.setting_name
        assert s['value'] == self.setting_value

    def test_list_settings(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        results, _ = self.sdk.settings.list()
        assert len(results) > 0
        assert any([r['name'] == self.setting_name for r in results])

    def test_get_setting(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        setting = self.sdk.settings.get(self.setting_key)
        assert setting is not None
        assert setting['name'] == self.setting_name
        assert setting['value'] == self.setting_value

    def test_delete_setting(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        self.sdk.settings.delete(self.setting_name)
        assert self.sdk.settings.get(self.setting_key) is None

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
