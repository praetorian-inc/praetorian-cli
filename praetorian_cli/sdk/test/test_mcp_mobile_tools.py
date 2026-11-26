"""The mobile dispatch path must be reachable over MCP through the same SDK methods.

13T-303 asks for this to be verified rather than assumed. The MCP server discovers SDK
methods and calls them with the JSON it was handed, coercing nothing -- so a method
whose parameter is a Python object is discoverable but not callable, and fails at the
first attribute access with the failure swallowed into a text response. These tests
pin the properties that keep the mobile tools callable.
"""

import pytest

from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.entities.apks import Apks
from praetorian_cli.sdk.mcp_server import MCPServer, is_sensitive_tool

JSON_SCALARS = {'string', 'number', 'boolean', 'array'}


class FakeChariot:
    """Enough of a Chariot for tool discovery, which only introspects the entities."""

    def __init__(self):
        self.aegis = Aegis(None)
        self.apks = Apks(None)


def discovery_only_server():
    """An MCPServer with tool discovery run but no transport started."""
    return MCPServer(FakeChariot())


def tool_parameters(server, tool_name):
    tool = server.discovered_tools[tool_name]
    return server._extract_parameters_from_doc(tool['doc'], tool['signature'])


class TestMobileToolsAreExposed:

    def setup_method(self):
        self.server = discovery_only_server()

    def test_the_mobile_tools_are_discovered(self):
        for tool in ('aegis_run_job', 'apks_add', 'aegis_list'):
            assert tool in self.server.discovered_tools

    def test_the_mobile_tools_survive_the_default_allow_list(self):
        # Secret-bearing tools are withheld unless named exactly. Dispatching a
        # capability and registering an APK carry no secrets, so they stay reachable
        # with no allow-list configured -- which is how the MCP server usually runs.
        for tool in ('aegis_run_job', 'apks_add'):
            assert not is_sensitive_tool(tool)
            assert self.server._is_tool_allowed(tool)

    def test_run_job_dispatches_on_values_an_mcp_client_can_send(self):
        parameters = tool_parameters(self.server, 'aegis_run_job')

        # Everything needed to dispatch is a scalar or a list. `agent` is the legacy
        # Agent argument, kept for positional callers; an MCP client never sends it.
        for name in ('hostname', 'package', 'endpoint_id', 'config'):
            assert parameters[name]['type'] == 'string', f'{name} is not expressible as JSON'
        # Advertised as an array, so a client sends ["android-device-survey"] rather than a
        # bare string whose characters would each be read as a capability name.
        assert parameters['capabilities']['type'] == 'array'

    def test_run_job_needs_no_required_argument_to_list_capabilities(self):
        parameters = tool_parameters(self.server, 'aegis_run_job')

        assert not [name for name, p in parameters.items() if p.get('required')]

    def test_every_run_job_parameter_is_documented(self):
        parameters = tool_parameters(self.server, 'aegis_run_job')

        # The description is what an agent reads to decide how to call the tool. The
        # fallback is the parameter's own name, which tells it nothing.
        for name, parameter in parameters.items():
            assert parameter['description'] != f'Parameter {name}'

    def test_apk_upload_is_a_single_tool_call(self):
        parameters = tool_parameters(self.server, 'apks_add')

        assert parameters['local_filepath']['type'] == 'string'
        assert parameters['local_filepath']['required'] is True
        assert parameters['chariot_filepath']['required'] is False


class TestOptionalTypeSpellings:

    def setup_method(self):
        self.server = discovery_only_server()

    def test_optional_spellings_keep_the_inner_json_type(self):
        for spelling in ('list or None', 'Optional[list]', 'list | None', 'List or None'):
            assert self.server._sphinx_type_to_json_type(spelling) == 'array', spelling
        assert self.server._sphinx_type_to_json_type('dict or None') == 'object'
        assert self.server._sphinx_type_to_json_type('str or None') == 'string'

    def test_run_job_schema_accepts_a_capability_list(self):
        import jsonschema

        schema = self.server._input_schema_for(self.server.discovered_tools['aegis_run_job'])

        jsonschema.validate({'capabilities': ['android-device-survey'],
                             'package': 'com.bank.app'}, schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({'capabilities': 'android-device-survey'}, schema)
