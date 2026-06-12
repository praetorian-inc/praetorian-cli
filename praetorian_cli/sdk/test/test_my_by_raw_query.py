import json
from unittest.mock import MagicMock

import pytest

from praetorian_cli.sdk.chariot import Chariot


def mock_response(body, status_code=200):
    resp = MagicMock()
    resp.ok = status_code < 400
    resp.status_code = status_code
    resp.text = json.dumps(body)
    resp.json.return_value = body
    return resp


def make_sdk(responses):
    sdk = Chariot.__new__(Chariot)
    sdk.url = lambda path: f'https://example.test{path}'
    sdk.chariot_request = MagicMock(side_effect=responses)
    return sdk


@pytest.mark.coherence
class TestMyByRawQuery:

    def test_tree_list_response(self):
        # tree=true queries return a bare JSON array of nodes, not a keyed dict
        nodes = [{'key': '#risk#1'}, {'key': '#risk#2'}]
        sdk = make_sdk([mock_response(nodes)])

        result = sdk.my_by_raw_query({'node': {'labels': ['Risk']}}, params={'tree': 'true'})

        assert result == nodes
        assert sdk.chariot_request.call_count == 1

    def test_tree_list_response_empty(self):
        sdk = make_sdk([mock_response([])])

        result = sdk.my_by_raw_query({'node': {'labels': ['Risk']}}, params={'tree': 'true'})

        assert result == []

    def test_dict_response_unchanged(self):
        body = {'risks': [{'key': '#risk#1'}]}
        sdk = make_sdk([mock_response(body)])

        result = sdk.my_by_raw_query({'node': {'labels': ['Risk']}})

        assert result == {'risks': [{'key': '#risk#1'}]}

    def test_dict_response_pagination(self):
        page1 = {'risks': [{'key': '#risk#1'}], 'offset': '1'}
        page2 = {'risks': [{'key': '#risk#2'}]}
        sdk = make_sdk([mock_response(page1), mock_response(page2)])

        result = sdk.my_by_raw_query({'node': {'labels': ['Risk']}}, pages=2)

        assert result['risks'] == [{'key': '#risk#1'}, {'key': '#risk#2'}]
        assert 'offset' not in result
        assert sdk.chariot_request.call_count == 2

    def test_dict_response_offset_preserved_when_pages_exhausted(self):
        page1 = {'risks': [{'key': '#risk#1'}], 'offset': '1'}
        sdk = make_sdk([mock_response(page1)])

        result = sdk.my_by_raw_query({'node': {'labels': ['Risk']}}, pages=1)

        assert result['risks'] == [{'key': '#risk#1'}]
        assert result['offset'] == '1'
