"""The mobile dispatch path must be reachable over MCP through the same SDK methods.

13T-303 asks for this to be verified rather than assumed. The MCP server discovers SDK
methods and calls them with the JSON it was handed, coercing nothing -- so a method
whose parameter is a Python object is discoverable but not callable, and fails at the
first attribute access with the failure swallowed into a text response. These tests
pin the properties that keep the mobile tools callable.
"""

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
    """An MCPServer with tool discovery run but no transport registered.

    MCPServer.__init__ also binds handlers onto the mcp library's Server, whose API
    differs across major versions of that library. These tests are about the SDK surface
    the tools are generated from, so they skip that binding rather than track it.
    """
    server = MCPServer.__new__(MCPServer)
    server.chariot = FakeChariot()
    server.allowable_tools = None
    server.discovered_tools = {}
    server._discover_tools()
    return server


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
        for name in ('capabilities', 'hostname', 'package', 'endpoint_id', 'config'):
            assert parameters[name]['type'] in JSON_SCALARS, f'{name} is not expressible as JSON'

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
