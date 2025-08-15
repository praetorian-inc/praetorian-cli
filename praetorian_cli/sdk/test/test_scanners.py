import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestScanners:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_get_scanner_by_key(self):
        result = self.sdk.scanners.get(self.scanner_key)
        if result:
            assert 'key' in result
            assert result['key'] == self.scanner_key

    def test_get_scanner_nonexistent(self):
        nonexistent_key = '#scanner#192.168.999.999'
        result = self.sdk.scanners.get(nonexistent_key)
        assert result is None

    def test_list_scanners_no_filter(self):
        results, _ = self.sdk.scanners.list()
        assert isinstance(results, list)

    def test_list_scanners_with_filter(self):
        results, _ = self.sdk.scanners.list(filter='127.0.0.1')
        assert isinstance(results, list)

    def test_list_scanners_with_pagination(self):
        results, _ = self.sdk.scanners.list(page_size=10)
        assert isinstance(results, list)
        assert len(results) <= 10

    def test_list_scanners_with_offset(self):
        results, _ = self.sdk.scanners.list(offset='test-offset')
        assert isinstance(results, list)

    def test_list_scanners_default_search_term(self):
        results, _ = self.sdk.scanners.list()
        assert isinstance(results, list)

    def teardown_class(self):
        pass
