import unittest
from unittest.mock import MagicMock, Mock

from praetorian_cli.sdk.entities.ports import Ports


class TestPorts(unittest.TestCase):

    def setUp(self):
        # Mock the API client
        self.mock_api = MagicMock()
        self.ports = Ports(self.mock_api)

    def test_get_success(self):
        """Test successful port retrieval by key"""
        # Arrange
        expected_port = {
            'key': '#port#tcp#443#asset#example.com#example.com',
            'username': 'test@example.com',
            'protocol': 'tcp',
            'port': 443,
            'service': 'https',
            'source': '#asset#example.com#example.com',
            'status': 'A',
            'created': '2023-10-27T10:00:00Z',
            'visited': '2023-10-27T11:00:00Z',
            'ttl': 1706353200
        }
        self.mock_api.search.by_exact_key.return_value = expected_port
        
        # Act
        result = self.ports.get('#port#tcp#443#asset#example.com#example.com')
        
        # Assert
        self.assertEqual(result, expected_port)
        self.mock_api.search.by_exact_key.assert_called_once_with('#port#tcp#443#asset#example.com#example.com')

    def test_get_not_found(self):
        """Test port retrieval when port doesn't exist"""
        # Arrange
        self.mock_api.search.by_exact_key.return_value = None
        
        # Act
        result = self.ports.get('#port#tcp#999#asset#nonexistent.com#nonexistent.com')
        
        # Assert
        self.assertIsNone(result)

    def test_list_all_ports(self):
        """Test listing all ports without filters"""
        # Arrange
        expected_ports = [
            {
                'key': '#port#tcp#443#asset#example.com#example.com',
                'protocol': 'tcp',
                'port': 443,
                'service': 'https'
            },
            {
                'key': '#port#tcp#22#asset#example.com#example.com',
                'protocol': 'tcp', 
                'port': 22,
                'service': 'ssh'
            }
        ]
        expected_offset = 'next_page_offset'
        self.mock_api.search.by_prefix.return_value = (expected_ports, expected_offset)
        
        # Act
        ports, offset = self.ports.list()
        
        # Assert
        self.assertEqual(ports, expected_ports)
        self.assertEqual(offset, expected_offset)
        self.mock_api.search.by_prefix.assert_called_once_with('port', '', offset=None, pages=1)

    def test_list_with_prefix_filter(self):
        """Test listing ports with prefix filter"""
        # Arrange
        expected_ports = [
            {
                'key': '#port#tcp#443#asset#example.com#example.com',
                'protocol': 'tcp',
                'port': 443,
                'service': 'https'
            }
        ]
        self.mock_api.search.by_prefix.return_value = (expected_ports, None)
        
        # Act
        ports, offset = self.ports.list(prefix_filter='tcp#443')
        
        # Assert
        self.assertEqual(ports, expected_ports)
        self.assertIsNone(offset)
        self.mock_api.search.by_prefix.assert_called_once_with('port', 'tcp#443', offset=None, pages=1)

    def test_list_by_source_key(self):
        """Test listing ports for a specific asset"""
        # Arrange
        expected_ports = [
            {
                'key': '#port#tcp#443#asset#example.com#example.com',
                'protocol': 'tcp',
                'port': 443,
                'service': 'https'
            },
            {
                'key': '#port#tcp#22#asset#example.com#example.com', 
                'protocol': 'tcp',
                'port': 22,
                'service': 'ssh'
            }
        ]
        self.mock_api.search.by_source.return_value = (expected_ports, None)
        
        # Act
        ports, offset = self.ports.list(source_key='#asset#example.com#example.com')
        
        # Assert
        self.assertEqual(ports, expected_ports)
        self.assertIsNone(offset)
        self.mock_api.search.by_source.assert_called_once_with('#asset#example.com#example.com', entity_type='port', offset=None, pages=1)

    def test_list_with_pagination(self):
        """Test listing ports with pagination parameters"""
        # Arrange
        expected_ports = []
        expected_offset = 'page_2_offset'
        self.mock_api.search.by_prefix.return_value = (expected_ports, expected_offset)
        
        # Act
        ports, offset = self.ports.list(prefix_filter='tcp', offset='page_1_offset', pages=5)
        
        # Assert
        self.assertEqual(ports, expected_ports)
        self.assertEqual(offset, expected_offset)
        self.mock_api.search.by_prefix.assert_called_once_with('port', 'tcp', offset='page_1_offset', pages=5)


if __name__ == '__main__':
    unittest.main()