import pytest

from praetorian_cli.sdk.entities.asset import Asset
from praetorian_cli.sdk.test.utils import make_test_values, setup_chariot


@pytest.mark.coherence
class TestWebApplication:
    """Test suite for the WebApplication entity class."""

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_add_webapplication(self):
        """Test adding a WebApplication with both URL and name provided."""
        result = self.sdk.webapplication.add(self.webapp_url, self.webapp_name)
        
        assert result is not None
        assert result.get('key') == self.webapp_key
        assert result.get('url') == self.webapp_url
        assert result.get('name') == self.webapp_name
        assert result.get('status') == Asset.ACTIVE.value

    def test_get_webapplication(self):
        """Test retrieving a WebApplication by key."""
        result = self.sdk.webapplication.get(self.webapp_key)
        
        assert result is not None
        assert result.get('key') == self.webapp_key
        assert result.get('url') == self.webapp_url
        assert result.get('name') == self.webapp_name
        assert result.get('status') == Asset.ACTIVE.value

    def test_list_webapplications(self):
        """Test listing WebApplications."""
        results, offset = self.sdk.webapplication.list(filter=self.webapp_url[len(self.webapp_url//2):])
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert any(r.get('key') == self.webapp_key for r in results)
        assert any(r.get('url') == self.webapp_url for r in results)

    def test_add_webapplication_empty_url_raises_exception(self):
        """Test that adding a WebApplication with empty URL raises an exception."""
        with pytest.raises(Exception, match="URL is required for WebApplication"):
            self.sdk.webapplication.add("")

    def test_add_webapplication_none_url_raises_exception(self):
        """Test that adding a WebApplication with None URL raises an exception."""
        with pytest.raises(Exception, match="URL is required for WebApplication"):
            self.sdk.webapplication.add(None)