import inspect
import json
import anyio
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
        self._discover_tools()
        self._register_tools()

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

                if self.allowable_tools and tool_name not in self.allowable_tools:
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
        
        sphinx_params = self._parse_sphinx_docstring(doc)
        if sphinx_params:
            for param_name, param_info in sphinx_params.items():
                if param_name in parameters:
                    if 'description' in param_info:
                        parameters[param_name]['description'] = param_info['description']
                    if 'type' in param_info:
                        parameters[param_name]['type'] = param_info['type']
        else:
            arguments_params = self._parse_arguments_section(doc, signature)
            for param_name, param_info in arguments_params.items():
                if param_name in parameters:
                    parameters[param_name]['description'] = param_info['description']
                    parameters[param_name]['type'] = param_info['type']
        
        return parameters

    def _parse_sphinx_docstring(self, doc: str) -> Dict[str, Dict[str, str]]:
        """Parse Sphinx-style docstrings with :param: and :type: directives"""
        import re
        
        parameters = {}
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
        
        return parameters if parameters else None

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

    def _parse_arguments_section(self, doc: str, signature: inspect.Signature) -> Dict[str, Any]:
        """Parse legacy Arguments: section format for backward compatibility"""
        parameters = {}
        
        lines = doc.split('\n')
        in_arguments_section = False
        current_param = None
        current_description = []
        
        for line in lines:
            line = line.strip()
            
            if line.lower().startswith('arguments:'):
                in_arguments_section = True
                continue
                
            if in_arguments_section:
                if line == '' and current_param:
                    if current_param in signature.parameters:
                        param = signature.parameters[current_param]
                        param_type = self._get_param_type(param)
                        parameters[current_param] = {
                            "type": param_type,
                            "description": ' '.join(current_description).strip(),
                            "required": param.default == inspect.Parameter.empty
                        }
                    current_param = None
                    current_description = []
                elif ':' in line and not line.startswith(' '):
                    if current_param:
                        if current_param in signature.parameters:
                            param = signature.parameters[current_param]
                            param_type = self._get_param_type(param)
                            parameters[current_param] = {
                                "type": param_type,
                                "description": ' '.join(current_description).strip(),
                                "required": param.default == inspect.Parameter.empty
                            }
                    
                    parts = line.split(':', 1)
                    current_param = parts[0].strip()
                    if len(parts) > 1:
                        current_description = [parts[1].strip()]
                    else:
                        current_description = []
                elif current_param and line:
                    current_description.append(line)
                elif not line:
                    continue
                else:
                    break
        
        if current_param and current_param in signature.parameters:
            param = signature.parameters[current_param]
            param_type = self._get_param_type(param)
            parameters[current_param] = {
                "type": param_type,
                "description": ' '.join(current_description).strip(),
                "required": param.default == inspect.Parameter.empty
            }
        
        return parameters

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
                        "type": param_info["type"],
                        "description": param_info["description"]
                    }
                    
                    if param_info["required"]:
                        required.append(param_name)
                
                tool_schema = {
                    "type": "object",
                    "properties": properties
                }
                
                if required:
                    tool_schema["required"] = required
                
                description = tool_info['doc'].split('\n')[0] if tool_info['doc'] else f"Execute {tool_name}"
                
                tool = Tool(
                    name=tool_name,
                    description=description,
                    inputSchema=tool_schema
                )
                
                tools.append(tool)
            
            return tools

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

    async def start(self):
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            return await self._call_tool(name, arguments)
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
