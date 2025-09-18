import pytest

from praetorian_cli.sdk.test.utils import make_test_values, setup_chariot


@pytest.mark.coherence
class TestWebpage:
    """Test suite for the Webpage entity class."""

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_webpage(self):
        """Test adding a Webpage with URL provided."""
        result = self.sdk.webpage.add(self.webpage_url)
        
        assert result is not None
        webpage = result.get('webpages')[0]
        assert webpage.get('key') == self.webpage_key
        assert webpage.get('url') == self.webpage_url

    def test_get_webpage(self):
        """Test retrieving a Webpage by key."""
        result = self.sdk.webpage.get(self.webpage_key)
        assert result is not None
        assert result.get('key') == self.webpage_key
        assert result.get('url') == self.webpage_url

    def test_list_webpages(self):
        """Test listing Webpages."""
        results, offset = self.sdk.webpage.list(filter=self.webpage_url[:len(self.webpage_url)//2])
        assert isinstance(results, list)
        assert len(results) > 0
        assert any(r.get('key') == self.webpage_key for r in results)
        assert any(r.get('url') == self.webpage_url for r in results)

    def test_add_webpage_empty_url_raises_exception(self):
        """Test that adding a Webpage with empty URL raises an exception."""
        with pytest.raises(Exception, match="URL is required for Webpage"):
            self.sdk.webpage.add("")

    def test_add_webpage_none_url_raises_exception(self):
        """Test that adding a Webpage with None URL raises an exception."""
        with pytest.raises(Exception, match="URL is required for Webpage"):
            self.sdk.webpage.add(None)
