import inspect
import json
import jsonschema
import anyio
import re
import fnmatch
from typing import Any, Dict, List, Optional, Callable
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

# Tool-name patterns classified as sensitive: their tools return or manage
# secret material (credential-broker payloads, API-key secrets, the webhook
# auth PIN, integration records that embed that PIN) or change account
# membership. A sensitive tool never matches a wildcard allow pattern: it is
# exposed only when an allow entry names it exactly. When adding a new entity
# or method to the SDK that returns or manages secret material, add its family
# to this tuple — nothing detects an unclassified secret-bearing tool
# automatically.
SENSITIVE_TOOL_PATTERNS = (
    'accounts_*',
    'credentials_*',
    'integrations_*',
    'keys_*',
    'webhook_*',
)


def is_sensitive_tool(tool_name: str) -> bool:
    return any(fnmatch.fnmatch(tool_name, pattern) for pattern in SENSITIVE_TOOL_PATTERNS)


class MCPServer:
    def __init__(self, chariot_instance, allowable_tools: Optional[List[str]] = None):
        self.chariot = chariot_instance
        self.allowable_tools = allowable_tools
        self.discovered_tools = {}
        self._discover_tools()
        # mcp >= 2 takes request handlers as constructor arguments. The 1.x
        # @server.list_tools() / @server.call_tool() decorators it replaced no
        # longer exist, so binding them late raised AttributeError on import.
        self.server = Server(
            "praetorian-cli",
            on_list_tools=self._on_list_tools,
            on_call_tool=self._on_call_tool,
        )

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Two-tier allow check: sensitive tools (SENSITIVE_TOOL_PATTERNS) are
        exposed only by an exact-name allow entry — wildcards never match them,
        and a None/empty allowlist exposes none of them; non-sensitive tools keep the
        original semantics (no allowlist means allowed, otherwise fnmatch
        against the allow patterns)."""
        if is_sensitive_tool(tool_name):
            return bool(self.allowable_tools) and tool_name in self.allowable_tools

        if not self.allowable_tools:
            return True

        return any(fnmatch.fnmatch(tool_name, pattern) for pattern in self.allowable_tools)

    def _discover_tools(self):
        excluded_methods = {'start_mcp_server', 'api'}

        for entity_name in dir(self.chariot):
            if entity_name.startswith('_'):
                continue
                
            entity_obj = getattr(self.chariot, entity_name)
            
            if not hasattr(entity_obj, '__class__') or not hasattr(entity_obj, 'api'):
                continue
                
            for method_name in dir(entity_obj):
                if method_name.startswith('_') or method_name in excluded_methods:
                    continue
                    
                method = getattr(entity_obj, method_name)
                if not callable(method):
                    continue
                    
                tool_name = f"{entity_name}_{method_name}"

                if not self._is_tool_allowed(tool_name):
                    continue

                try:
                    sig = inspect.signature(method)
                    doc = inspect.getdoc(method) or ""
                    
                    self.discovered_tools[tool_name] = {
                        'method': method,
                        'signature': sig,
                        'doc': doc,
                        'entity': entity_name,
                        'method_name': method_name
                    }
                except Exception:
                    continue

    def _extract_parameters_from_doc(self, doc: str, signature: inspect.Signature) -> Dict[str, Any]:
        parameters = {}
        
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
                
            parameters[param_name] = {
                "type": self._get_param_type(param),
                "description": f"Parameter {param_name}",
                "required": param.default == inspect.Parameter.empty
            }

        lines = doc.split('\n')
        for line in lines:
            line = line.strip()

            param_match = re.match(r':param\s+(\w+):\s*(.*)', line)
            if param_match:
                param_name = param_match.group(1)
                description = param_match.group(2)
                if param_name not in parameters:
                    parameters[param_name] = {}
                parameters[param_name]['description'] = description
                continue

            type_match = re.match(r':type\s+(\w+):\s*(.*)', line)
            if type_match:
                param_name = type_match.group(1)
                param_type = self._sphinx_type_to_json_type(type_match.group(2))
                if param_name not in parameters:
                    parameters[param_name] = {}
                parameters[param_name]['type'] = param_type
                continue

        return parameters

    def _sphinx_type_to_json_type(self, sphinx_type: str) -> str:
        """Convert Sphinx type annotations to JSON schema types"""
        sphinx_type = sphinx_type.lower().strip()
        
        if sphinx_type in ['str', 'string']:
            return "string"
        elif sphinx_type in ['int', 'integer']:
            return "number"
        elif sphinx_type in ['bool', 'boolean']:
            return "boolean"
        elif sphinx_type in ['list', 'array']:
            return "array"
        elif sphinx_type in ['dict', 'object']:
            return "object"
        else:
            return "string"

    def _get_param_type(self, param: inspect.Parameter) -> str:
        if param.annotation != inspect.Parameter.empty:
            if param.annotation == str:
                return "string"
            elif param.annotation == int:
                return "number"
            elif param.annotation == bool:
                return "boolean"
            elif param.annotation == list:
                return "array"
            elif param.annotation == dict:
                return "object"
        
        if param.default != inspect.Parameter.empty:
            if isinstance(param.default, str):
                return "string"
            elif isinstance(param.default, int):
                return "number"
            elif isinstance(param.default, bool):
                return "boolean"
            elif isinstance(param.default, list):
                return "array"
            elif isinstance(param.default, dict):
                return "object"
        
        return "string"

    def _input_schema_for(self, tool_info) -> Dict[str, Any]:
        """The JSON Schema advertised for one tool.

        Shared with _on_call_tool so the schema arguments are checked against is
        necessarily the one the client was shown — a second derivation here
        could drift from what tools/list promised.
        """
        parameters = self._extract_parameters_from_doc(tool_info['doc'], tool_info['signature'])

        properties = {}
        required = []

        for param_name, param_info in parameters.items():
            if param_name == 'self':
                continue

            properties[param_name] = {
                "type": param_info.get("type", "string"),
                "description": param_info.get("description", f"Parameter {param_name}")
            }

            if param_info.get("required", False):
                required.append(param_name)

        tool_schema = {
            "type": "object",
            "properties": properties
        }

        if required:
            tool_schema["required"] = required

        return tool_schema

    async def _on_list_tools(self, context: ServerRequestContext,
                             params: Optional[PaginatedRequestParams] = None) -> ListToolsResult:
        tools = []
        for tool_name, tool_info in self.discovered_tools.items():
            parts = tool_info["doc"].split("\n")
            description = parts[0]
            if len(parts) > 1:
                description += "\n"
                description += "\t".join(parts[1:])

            tools.append(Tool(
                name=tool_name,
                description=description,
                input_schema=self._input_schema_for(tool_info),
            ))

        return ListToolsResult(tools=tools)

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name not in self.discovered_tools:
            return [TextContent(type="text", text=f"Tool {name} not found")]
        
        tool_info = self.discovered_tools[name]
        method = tool_info['method']
        
        try:
            filtered_args = {}
            sig = tool_info['signature']
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                if param_name in arguments:
                    filtered_args[param_name] = arguments[param_name]
                elif param.default == inspect.Parameter.empty:
                    return [TextContent(type="text", text=f"Missing required parameter: {param_name}")]
            
            result = method(**filtered_args)
            
            if result is None:
                return [TextContent(type="text", text="Operation completed successfully")]
            
            result_str = json.dumps(result, indent=2, default=str)
            return [TextContent(type="text", text=result_str)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

    async def _on_call_tool(self, context: ServerRequestContext,
                            params: CallToolRequestParams) -> CallToolResult:
        arguments = params.arguments or {}

        # mcp 1.x validated arguments against the advertised inputSchema before
        # dispatch: Server.call_tool() defaulted to validate_input=True and
        # returned an isError result on failure. The 2.x low-level server does
        # not — only its high-level MCPServer does, from Python signatures — so
        # the check lives here. Without it a wrong-typed argument reaches the
        # SDK method and becomes a live API call against the user's account.
        #
        # An unknown name falls through deliberately: _call_tool owns that
        # error, and there is no schema to check against.
        tool_info = self.discovered_tools.get(params.name)
        if tool_info is not None:
            try:
                jsonschema.validate(instance=arguments, schema=self._input_schema_for(tool_info))
            except jsonschema.ValidationError as e:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Input validation error: {e.message}")],
                    is_error=True,
                )

        return CallToolResult(content=await self._call_tool(params.name, arguments))

    async def start(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
