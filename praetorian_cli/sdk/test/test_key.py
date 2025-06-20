import pytest
import datetime

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestKey:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_key(self):
        k = self.sdk.keys.add(self.key_name, self.expires())
        assert k is not None
        assert k['name'] == self.key_name
        assert 'key' in k
        assert len(k['key']) > 5
        assert k['key'].startswith('#key#')

    def test_list_keys(self):
        self.sdk.keys.add(self.key_name, self.expires())
        results, _ = self.sdk.keys.list()
        assert len(results) > 0
        assert any([r['name'] == self.key_name for r in results])

    def test_get_key(self):
        k = self.sdk.keys.add(self.key_name, self.expires())
        key = self.sdk.keys.get(k['key'])
        assert key is not None
        assert key['name'] == k['name']
        assert key['key'] == k['key']

    def test_delete_key(self):
        k = self.sdk.keys.add(self.key_name, self.expires())
        self.sdk.keys.delete(k['key'])
        self.sdk.keys.get(k['key'])['status'] = 'D'

    def expires(self):
        expiresT = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
        return expiresT.strftime('%Y-%m-%dT%H:%M:%SZ')

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
