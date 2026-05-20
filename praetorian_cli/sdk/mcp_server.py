import inspect
import json
import anyio
import re
import fnmatch
from typing import Any, Dict, List, Optional, Callable
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

class MCPServer:
    def __init__(self, chariot_instance, allowable_tools: Optional[List[str]] = None):
        self.chariot = chariot_instance
        self.allowable_tools = allowable_tools
        self.server = Server("praetorian-cli")
        self.discovered_tools = {}
        self._module_tools = {}
        self._discover_tools()
        self._define_module_tools()
        self._register_tools()

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool_name matches any of the allowed patterns using wildcards"""
        if fnmatch.fnmatch(tool_name, "*accounts*"):
            return False

        if not self.allowable_tools:
            return True
        
        for pattern in self.allowable_tools:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

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

    def _define_module_tools(self):
        """Populate self._module_tools with explicit module management MCP tools."""
        self._module_tools["list_modules"] = Tool(
            name="list_modules",
            description="List all available Guard security modules with install status. "
                        "Returns name, category, description, install status, and version for each module.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (matches name, description, tags)"},
                    "category": {"type": "string", "description": "Filter by category (scanner, credential, recon, cloud, cicd, ai, supply-chain, api)"},
                },
            },
        )

        self._module_tools["module_info"] = Tool(
            name="module_info",
            description="Get full details for a Guard security module including options, version, and install path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name (e.g., brutus, nuclei, titus)"},
                },
                "required": ["name"],
            },
        )

        self._module_tools["install_module"] = Tool(
            name="install_module",
            description="Install a Guard security module binary from GitHub releases to ~/.praetorian/bin/.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name to install, or 'all'"},
                    "force": {"type": "boolean", "description": "Reinstall even if already present"},
                },
                "required": ["name"],
            },
        )

        self._module_tools["run_module"] = Tool(
            name="run_module",
            description="Execute an installed Guard security module against a target. "
                        "The module must be installed first (use install_module).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name"},
                    "target": {"type": "string", "description": "Target (IP, domain, URL, or Guard key)"},
                    "options": {"type": "object", "description": "Tool-specific options as key-value pairs"},
                },
                "required": ["name", "target"],
            },
        )

    def _register_tools(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            tools = []
            for tool_name, tool_info in self.discovered_tools.items():
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

                parts = tool_info["doc"].split("\n")
                description = parts[0]
                if len(parts) > 1:
                    description += "\n"
                    description += "\t".join(parts[1:])

                tool = Tool(
                    name=tool_name,
                    description=description,
                    inputSchema=tool_schema
                )

                tools.append(tool)

            # Add module management tools
            tools.extend(self._module_tools.values())

            return tools

    async def _handle_module_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "list_modules":
                from praetorian_cli.registry import get_registry
                from praetorian_cli.runners.local import list_installed
                reg = get_registry()
                query = arguments.get("query", "")
                category = arguments.get("category", "")
                results = reg.search_modules(query, category=category)
                installed = list_installed()
                for r in results:
                    r["installed"] = r["name"] in installed
                    ver = reg.get_version(r["name"])
                    r["version"] = ver["version"] if ver else None
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "module_info":
                from praetorian_cli.registry import get_registry
                from praetorian_cli.runners.local import is_installed, get_binary_path
                if not arguments.get("name"):
                    return [TextContent(type="text", text="Missing required parameter: name")]
                reg = get_registry()
                mod_name = arguments["name"].lower()
                mod = reg.get_module(mod_name)
                if not mod:
                    return [TextContent(type="text", text=f"Unknown module: {mod_name}")]
                ver = reg.get_version(mod_name)
                out = {"name": mod_name, **mod}
                out["installed"] = is_installed(mod_name)
                out["version"] = ver["version"] if ver else None
                out["binary_path"] = get_binary_path(mod_name)
                return [TextContent(type="text", text=json.dumps(out, indent=2))]

            elif name == "install_module":
                from praetorian_cli.runners.local import install_tool, is_installed
                if not arguments.get("name"):
                    return [TextContent(type="text", text="Missing required parameter: name")]
                mod_name = arguments["name"].lower()
                force = arguments.get("force", False)
                if not force and is_installed(mod_name):
                    return [TextContent(type="text", text=json.dumps({"name": mod_name, "status": "already_installed"}))]
                path = install_tool(mod_name, force=force)
                return [TextContent(type="text", text=json.dumps({"name": mod_name, "status": "installed", "path": path}))]

            elif name == "run_module":
                from praetorian_cli.runners.local import LocalRunner, get_tool_plugin, is_installed
                if not arguments.get("name") or not arguments.get("target"):
                    return [TextContent(type="text", text="Missing required parameter: name and target are required")]
                mod_name = arguments["name"].lower()
                target = arguments["target"]
                options = arguments.get("options", {})
                if not is_installed(mod_name):
                    return [TextContent(type="text", text=f"Module {mod_name} is not installed. Use install_module first.")]
                plugin = get_tool_plugin(mod_name)
                extra_config = json.dumps(options) if options else ""
                args = plugin.build_args(target, extra_config)
                runner = LocalRunner(mod_name)
                result = runner.run(args, timeout=300)
                out = {
                    "name": mod_name,
                    "target": target,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                return [TextContent(type="text", text=json.dumps(out, indent=2))]

            return [TextContent(type="text", text=f"Unknown module tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error in {name}: {str(e)}")]

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        # Handle module management tools
        if name in self._module_tools:
            return await self._handle_module_tool(name, arguments)

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

    async def start(self):
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            return await self._call_tool(name, arguments)
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
