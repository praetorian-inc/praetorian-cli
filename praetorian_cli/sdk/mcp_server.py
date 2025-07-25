import inspect, json, asyncio
import asyncio
from typing import Any, Dict, List, Optional, Callable
from mcp.server import Server
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
                    
                tool_name = f"{entity_name}.{method_name}"

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
        
        for param_name, param in signature.parameters.items():
            if param_name not in parameters and param_name != 'self':
                param_type = self._get_param_type(param)
                parameters[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}",
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
        print('starting')
        return
        # TODO
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            return await self._call_tool(name, arguments)

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())
