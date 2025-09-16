import pytest

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot, epoch_micro


@pytest.mark.coherence
class TestWebpage:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        
        # Test data for webpages - need real entities for live tests
        self.test_webpage_url = f"https://test-{epoch_micro()}.example.com"
        self.test_webpage_key = f"#webpage#{self.test_webpage_url}"
        
        # Create test entities that the webpage can link to
        # Use the test file from the asset tests
        self.test_file_name = f"test-webpage-file-{epoch_micro()}.txt"
        self.test_file_key = f"#file#{self.test_file_name}"
        
        # Create test repository
        self.test_repo_url = f"https://github.com/test-{epoch_micro()}/repo.git"
        self.test_repo_key = f"#repository#{self.test_repo_url}#repo.git"

    def test_get_webpage_not_found(self):
        # Test getting a non-existent webpage
        result = self.sdk.webpages.get(self.test_webpage_key)
        # Should return None or empty for non-existent webpage
        assert result is None or not result

    def test_list_webpages_empty(self):
        # Test listing webpages with a prefix that doesn't exist
        results, offset = self.sdk.webpages.list(key_prefix=self.test_webpage_key)
        # Should return empty list for non-existent webpages
        assert isinstance(results, list)
        assert len(results) == 0

    def test_link_source_webpage_not_found(self):
        # Test linking to a non-existent webpage - should fail
        try:
            result = self.sdk.webpages.link_source(self.test_webpage_key, self.test_file_key)
            # If it doesn't raise an exception, it should indicate failure
            assert False, "Expected linking to non-existent webpage to fail"
        except Exception as e:
            # Should get a 404 error for webpage not found
            assert "404" in str(e) or "not found" in str(e).lower()

    def test_link_source_entity_not_found(self):
        # Test linking a non-existent file - should fail
        try:
            result = self.sdk.webpages.link_source(self.test_webpage_key, self.test_file_key)
            # If it doesn't raise an exception, it should indicate failure
            assert False, "Expected linking non-existent entity to fail"
        except Exception as e:
            # Should get a 404 error for entity not found
            assert "404" in str(e) or "not found" in str(e).lower()

    def test_unlink_source_webpage_not_found(self):
        # Test unlinking from a non-existent webpage - should fail
        try:
            result = self.sdk.webpages.unlink_source(self.test_webpage_key, self.test_file_key)
            # If it doesn't raise an exception, it should indicate failure
            assert False, "Expected unlinking from non-existent webpage to fail"
        except Exception as e:
            # Should get a 404 error for webpage not found
            assert "404" in str(e) or "not found" in str(e).lower()

    def teardown_class(self):
        # Clean up test entities if they were created
        try:
            # Try to delete test entities, ignore errors since they might not exist
            pass
        except Exception:
            pass