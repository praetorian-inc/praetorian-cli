import pytest

from praetorian_cli.sdk.model.utils import setting_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestSettings:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_setting(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        settings, _ = self.sdk.settings.list(self.setting_name)
        assert len(settings) > 0
        assert settings[0]['name'] == self.setting_name
        assert settings[0]['value'] == self.setting_value

    def test_get_setting(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        setting = self.sdk.settings.get(self.setting_key)
        assert setting is not None
        assert setting['name'] == self.setting_name
        assert setting['value'] == self.setting_value

    def test_delete_setting(self):
        self.sdk.settings.add(self.setting_name, self.setting_value)
        self.sdk.settings.delete(self.setting_key)
        settings, _ = self.sdk.settings.list(self.setting_name)
        assert len(settings) == 0

    def teardown_class(self):
        clean_test_entities(self.sdk, self) 