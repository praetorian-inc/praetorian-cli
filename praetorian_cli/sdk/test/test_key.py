import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestKey:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_key(self):
        k = self.sdk.keys.add(self.key_name)
        assert k is not None
        assert k['name'] == self.key_name
        assert 'key' in k
        assert k['key'] == self.key_key

    def test_list_keys(self):
        self.sdk.keys.add(self.key_name)
        results, _ = self.sdk.keys.list()
        assert len(results) > 0
        assert any([r['name'] == self.key_name for r in results])

    def test_get_key(self):
        self.sdk.keys.add(self.key_name)
        key = self.sdk.keys.get(self.key_key)
        assert key is not None
        assert key['name'] == self.key_name
        assert key['key'] == self.key_key

    def test_delete_key(self):
        self.sdk.keys.add(self.key_name)
        self.sdk.keys.delete(self.key_key)
        assert self.sdk.keys.get(self.key_key) is None

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
