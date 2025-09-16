import pytest
from unittest.mock import Mock, MagicMock, patch
import requests

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestWebpage:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        
        # Test data for webpages
        self.webpage_url = "https://example.com/test"
        self.webpage_key = f"#webpage#{self.webpage_url}"
        self.file_key = "#file#proofs/test-scan.txt"
        self.repo_key = "#repository#https://github.com/test/repo.git#repo.git"

    def test_get_webpage(self):
        # Mock the search response
        with patch.object(self.sdk.search, 'by_exact_key') as mock_search:
            mock_search.return_value = {
                'key': self.webpage_key,
                'url': self.webpage_url,
                'sourceCode': []
            }
            
            result = self.sdk.webpages.get(self.webpage_key)
            
            assert result['key'] == self.webpage_key
            assert result['url'] == self.webpage_url
            mock_search.assert_called_once_with(self.webpage_key)

    def test_list_webpages(self):
        # Mock the search response
        with patch.object(self.sdk.search, 'by_query') as mock_search:
            mock_search.return_value = ([
                {'key': '#webpage#https://example.com', 'url': 'https://example.com'},
                {'key': '#webpage#https://example.com/page2', 'url': 'https://example.com/page2'}
            ], None)
            
            results, offset = self.sdk.webpages.list(key_prefix='#webpage#https://example.com')
            
            assert len(results) == 2
            assert results[0]['key'] == '#webpage#https://example.com'
            assert mock_search.called

    def test_link_source_success(self):
        # Mock the API request
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Entity linked successfully',
            'webpageKey': self.webpage_key,
            'entityKey': self.file_key,
            'sourceCode': [self.file_key]
        }
        
        with patch.object(self.sdk, '_make_request', return_value=mock_response) as mock_request:
            result = self.sdk.webpages.link_source(self.webpage_key, self.file_key)
            
            assert result['message'] == 'Entity linked successfully'
            assert result['entityKey'] == self.file_key
            assert self.file_key in result['sourceCode']
            
            mock_request.assert_called_once_with(
                'PUT',
                self.sdk.url('/webpage/link'),
                json={'webpageKey': self.webpage_key, 'entityKey': self.file_key}
            )

    def test_link_source_failure(self):
        # Mock a failed API request
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.text = 'Webpage not found'
        
        with patch.object(self.sdk, '_make_request', return_value=mock_response) as mock_request:
            with pytest.raises(Exception) as exc_info:
                self.sdk.webpages.link_source(self.webpage_key, self.file_key)
            
            assert 'Failed to link source' in str(exc_info.value)
            assert '404' in str(exc_info.value)
            assert 'Webpage not found' in str(exc_info.value)

    def test_unlink_source_success(self):
        # Mock the API request
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Entity unlinked successfully',
            'webpageKey': self.webpage_key,
            'entityKey': self.file_key,
            'sourceCode': []
        }
        
        with patch.object(self.sdk, '_make_request', return_value=mock_response) as mock_request:
            result = self.sdk.webpages.unlink_source(self.webpage_key, self.file_key)
            
            assert result['message'] == 'Entity unlinked successfully'
            assert result['entityKey'] == self.file_key
            assert result['sourceCode'] == []
            
            mock_request.assert_called_once_with(
                'DELETE',
                self.sdk.url('/webpage/link'),
                json={'webpageKey': self.webpage_key, 'entityKey': self.file_key}
            )

    def test_unlink_source_failure(self):
        # Mock a failed API request
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.text = 'Webpage not found'
        
        with patch.object(self.sdk, '_make_request', return_value=mock_response) as mock_request:
            with pytest.raises(Exception) as exc_info:
                self.sdk.webpages.unlink_source(self.webpage_key, self.file_key)
            
            assert 'Failed to unlink source' in str(exc_info.value)
            assert '404' in str(exc_info.value)
            assert 'Webpage not found' in str(exc_info.value)

    def test_link_repository_source(self):
        # Test linking a repository instead of a file
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Entity linked successfully',
            'webpageKey': self.webpage_key,
            'entityKey': self.repo_key,
            'sourceCode': [self.repo_key]
        }
        
        with patch.object(self.sdk, '_make_request', return_value=mock_response) as mock_request:
            result = self.sdk.webpages.link_source(self.webpage_key, self.repo_key)
            
            assert result['entityKey'] == self.repo_key
            assert self.repo_key in result['sourceCode']
            
            mock_request.assert_called_once_with(
                'PUT',
                self.sdk.url('/webpage/link'),
                json={'webpageKey': self.webpage_key, 'entityKey': self.repo_key}
            )