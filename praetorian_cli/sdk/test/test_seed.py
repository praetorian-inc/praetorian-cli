import pytest

from praetorian_cli.sdk.model.globals import Seed
from praetorian_cli.sdk.model.utils import seed_status
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestSeed:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_seed(self):
        seed = self.sdk.seeds.add(self.seed_dns)
        assert seed['key'] == self.seed_key

    def test_get_seed(self):
        a = self.get_seed()
        assert a['dns'] == self.seed_dns
        assert a['status'] == seed_status('domain', Seed.PENDING.value)

    def test_list_seed(self):
        results, _ = self.sdk.seeds.list('domain', self.seed_dns)
        assert len(results) == 1
        assert results[0]['dns'] == self.seed_dns

    def test_update_seed(self):
        self.sdk.seeds.update(self.seed_key, Seed.FROZEN.value)
        assert self.get_seed()['status'] == seed_status('domain', Seed.FROZEN.value)

    def test_delete_seed(self):
        self.sdk.seeds.delete(self.seed_key)
        assert self.sdk.seeds.get(self.seed_key)['status'] == seed_status('domain', Seed.DELETED.value)

    def get_seed(self):
        return self.sdk.seeds.get(self.seed_key)

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
