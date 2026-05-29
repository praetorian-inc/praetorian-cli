"""Tests for MCP list_modules / module_info using CapabilityCatalog."""

import asyncio
import json
from unittest.mock import patch, MagicMock

from praetorian_cli.catalog import Capability
from praetorian_cli.sdk.mcp_server import MCPServer

SAMPLE = [
    Capability.from_api({'Name': 'brutus', 'Category': ['credential'],
                         'Description': 'Credential tester', 'Version': '1.0.0'}),
    Capability.from_api({'Name': 'nuclei', 'Category': ['scanner'],
                         'Description': 'Vuln scanner', 'Version': '2.0.0'}),
]


class _FakeSDK:
    """Minimal SDK stub — MCPServer only reads .chariot attrs for _discover_tools;
    we don't need real entity objects since we're testing module tools only."""
    pass


def _make_server():
    return MCPServer(_FakeSDK())


# ---------------------------------------------------------------------------
# list_modules — returns all capabilities from CapabilityCatalog
# ---------------------------------------------------------------------------

def test_list_modules_returns_all_capabilities():
    server = _make_server()
    with patch('praetorian_cli.catalog.CapabilityCatalog.all', return_value=SAMPLE), \
         patch('praetorian_cli.runners.local.list_installed', return_value={}), \
         patch('praetorian_cli.registry.get_registry') as mock_reg:
        mock_reg.return_value.get_version.return_value = None
        result = asyncio.run(server._handle_module_tool('list_modules', {}))

    assert len(result) == 1
    data = json.loads(result[0].text)
    names = {item['name'] for item in data}
    assert names == {'brutus', 'nuclei'}


def test_list_modules_query_filter():
    """query param should narrow results to matching capabilities."""
    server = _make_server()
    with patch('praetorian_cli.catalog.CapabilityCatalog.all', return_value=SAMPLE), \
         patch('praetorian_cli.runners.local.list_installed', return_value={}), \
         patch('praetorian_cli.registry.get_registry') as mock_reg:
        mock_reg.return_value.get_version.return_value = None
        result = asyncio.run(server._handle_module_tool('list_modules', {'query': 'brutus'}))

    data = json.loads(result[0].text)
    assert len(data) == 1
    assert data[0]['name'] == 'brutus'


def test_list_modules_install_status():
    """installed flag should be True only for installed modules."""
    server = _make_server()
    with patch('praetorian_cli.catalog.CapabilityCatalog.all', return_value=SAMPLE), \
         patch('praetorian_cli.runners.local.list_installed',
               return_value={'brutus': '/usr/local/bin/brutus'}), \
         patch('praetorian_cli.registry.get_registry') as mock_reg:
        mock_reg.return_value.get_version.return_value = {'version': '1.0.0'}
        result = asyncio.run(server._handle_module_tool('list_modules', {}))

    data = json.loads(result[0].text)
    by_name = {item['name']: item for item in data}
    assert by_name['brutus']['installed'] is True
    assert by_name['nuclei']['installed'] is False


# ---------------------------------------------------------------------------
# module_info — returns detailed info for a single capability
# ---------------------------------------------------------------------------

def test_module_info_returns_capability_fields():
    server = _make_server()
    with patch('praetorian_cli.catalog.CapabilityCatalog.get',
               return_value=SAMPLE[0]), \
         patch('praetorian_cli.runners.local.is_installed', return_value=False), \
         patch('praetorian_cli.runners.local.get_binary_path', return_value=None), \
         patch('praetorian_cli.registry.get_registry') as mock_reg:
        mock_reg.return_value.get_version.return_value = {'version': '1.0.0'}
        mock_reg.return_value.is_local_only.return_value = False
        result = asyncio.run(server._handle_module_tool('module_info', {'name': 'brutus'}))

    data = json.loads(result[0].text)
    assert data['name'] == 'brutus'
    assert data['description'] == 'Credential tester'
    assert 'installed' in data
    assert 'version' in data
    assert 'binary_path' in data
    assert 'local_only' in data


def test_module_info_unknown_module():
    """Unknown module should return a helpful error message (not crash)."""
    server = _make_server()
    with patch('praetorian_cli.catalog.CapabilityCatalog.get', return_value=None):
        result = asyncio.run(server._handle_module_tool('module_info', {'name': 'nonexistent'}))

    assert 'Unknown module' in result[0].text


def test_module_info_missing_name_param():
    server = _make_server()
    result = asyncio.run(server._handle_module_tool('module_info', {}))
    assert 'Missing required parameter' in result[0].text


# ---------------------------------------------------------------------------
# install_module — name='all' installs every installable tool
# ---------------------------------------------------------------------------

def test_install_module_all_installs_each_tool():
    """install_module with name='all' should attempt each tool and return a list."""
    server = _make_server()
    calls = []

    def _stub_install(name, force=False):
        calls.append(name)
        return f'/bin/{name}'

    with patch('praetorian_cli.runners.local.install_tool', side_effect=_stub_install), \
         patch('praetorian_cli.runners.local.is_installed', return_value=False), \
         patch('praetorian_cli.runners.local.INSTALLABLE_TOOLS', {'brutus': {}, 'nuclei': {}}):
        result = asyncio.run(server._handle_module_tool('install_module', {'name': 'all'}))

    assert sorted(calls) == ['brutus', 'nuclei']
    data = json.loads(result[0].text)
    assert isinstance(data, list)
    names = {item['name'] for item in data}
    assert names == {'brutus', 'nuclei'}
    assert all(item['status'] == 'installed' for item in data)


def test_install_module_all_isolates_failures():
    """One tool failing must not abort the batch."""
    server = _make_server()

    def _stub_install(name, force=False):
        if name == 'brutus':
            raise RuntimeError('boom')
        return f'/bin/{name}'

    with patch('praetorian_cli.runners.local.install_tool', side_effect=_stub_install), \
         patch('praetorian_cli.runners.local.is_installed', return_value=False), \
         patch('praetorian_cli.runners.local.INSTALLABLE_TOOLS', {'brutus': {}, 'nuclei': {}}):
        result = asyncio.run(server._handle_module_tool('install_module', {'name': 'all'}))

    data = json.loads(result[0].text)
    by_name = {item['name']: item for item in data}
    assert by_name['brutus']['status'] == 'error'
    assert 'boom' in by_name['brutus']['error']
    assert by_name['nuclei']['status'] == 'installed'
