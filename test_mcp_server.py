#!/usr/bin/env python3
"""
Test script for MCP server functionality
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.mcp_server import MCPServer

def test_mcp_server_discovery():
    """Test that MCP server discovers SDK methods correctly"""
    print("Testing MCP server tool discovery...")
    
    try:
        keychain = Keychain('test')
        chariot = Chariot(keychain)
        
        server = MCPServer(chariot)
        
        print(f"Discovered {len(server.discovered_tools)} tools:")
        for tool_name in sorted(server.discovered_tools.keys()):
            tool_info = server.discovered_tools[tool_name]
            print(f"  - {tool_name}: {tool_info['doc'].split(chr(10))[0] if tool_info['doc'] else 'No description'}")
        
        print("\nTesting recursion prevention...")
        mcp_tools = [name for name in server.discovered_tools.keys() if 'start_mcp_server' in name]
        if mcp_tools:
            print(f"ERROR: Found MCP server method in tools: {mcp_tools}")
            return False
        else:
            print("SUCCESS: MCP server method correctly excluded from tools")
        
        print("\nTesting tool filtering...")
        filtered_server = MCPServer(chariot, allowable_tools=['assets.add', 'risks.list'])
        print(f"Filtered server has {len(filtered_server.discovered_tools)} tools:")
        for tool_name in sorted(filtered_server.discovered_tools.keys()):
            print(f"  - {tool_name}")
        
        expected_tools = {'assets.add', 'risks.list'}
        actual_tools = set(filtered_server.discovered_tools.keys())
        if actual_tools == expected_tools:
            print("SUCCESS: Tool filtering works correctly")
        else:
            print(f"ERROR: Expected {expected_tools}, got {actual_tools}")
            return False
        
        print("\nTesting parameter extraction...")
        if 'assets.add' in server.discovered_tools:
            tool_info = server.discovered_tools['assets.add']
            params = server._extract_parameters_from_doc(tool_info['doc'], tool_info['signature'])
            print(f"Parameters for assets.add: {list(params.keys())}")
            if len(params) > 0:
                print("SUCCESS: Parameter extraction works correctly")
            else:
                print(f"ERROR: No parameters extracted for assets.add")
                return False
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mcp_server_discovery()
    if success:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
