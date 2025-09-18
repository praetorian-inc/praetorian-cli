#!/usr/bin/env python3
"""Test tool execution validation"""

import uuid
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

def test_tool_validation():
    try:
        keychain = Keychain("United States", None)
        chariot = Chariot(keychain=keychain, proxy="")
        
        conversation_id = str(uuid.uuid4())
        
        print("=== Testing Query Tool Execution Validation ===")
        response = chariot._make_request("POST", chariot.url("/conversations"), json={
            "conversationId": conversation_id,
            "message": "Execute a query to find all active assets and show me the actual database results"
        })
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json().get('response', {})
            ai_response = result.get('response', 'No response')
            print(f"Full AI Response:")
            print("=" * 80)
            print(ai_response)
            print("=" * 80)
            
            # Detailed validation of tool execution
            validation_checks = {
                "Tool registration": "Failed to build query tool" not in ai_response,
                "Tool execution": "Query executed successfully" in ai_response,
                "Database results": "Found " in ai_response and " results:" in ai_response,
                "JSON output": "```json" in ai_response,
                "Error handling": "error" not in ai_response.lower()
            }
            
            print("\n=== Tool Execution Validation ===")
            for check, passed in validation_checks.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"{status} {check}")
            
            # Extract and validate result count if available
            if "Found " in ai_response:
                import re
                match = re.search(r'Found (\d+) results:', ai_response)
                if match:
                    count = int(match.group(1))
                    print(f"\n📊 Database returned {count} assets")
                    if count > 0:
                        print("✅ Real database query execution confirmed!")
                    else:
                        print("⚠️  Query executed but no assets found")
                        
            # Check for actual JSON data
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                if json_end > json_start:
                    json_content = ai_response[json_start:json_end].strip()
                    if len(json_content) > 100:  # Substantial JSON content
                        print("✅ Substantial JSON results returned from database!")
                    else:
                        print("⚠️  Minimal JSON content returned")
                        
        else:
            print(f"❌ API Error: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tool_validation()