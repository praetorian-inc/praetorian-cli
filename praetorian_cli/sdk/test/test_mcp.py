import pytest

from praetorian_cli.sdk.mcp_server import MCPServer
from praetorian_cli.sdk.test.utils import setup_chariot, make_test_values, clean_test_entities


@pytest.mark.coherence
class TestMCP:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_mcp_default(self):
        mcp = MCPServer(self.sdk)
        assert 'search_by_term' in mcp.discovered_tools
        assert len(mcp.discovered_tools['search_by_term']['doc']) > 0
        assert 'assume_role' not in mcp.discovered_tools

    def test_mcp_configurable(self):
        mcp = MCPServer(self.sdk, ['risks_*'])
        assert 'search_by_term' not in mcp.discovered_tools
        assert 'risks_add' in mcp.discovered_tools
        assert len(mcp.discovered_tools['risks_add']['doc']) > 0
        assert 'assume_role' not in mcp.discovered_tools

    def teardown_class(self):
        clean_test_entities(self.sdk, self)