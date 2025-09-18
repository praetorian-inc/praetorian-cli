#!/usr/bin/env python3
"""Test script for conversation functionality"""

import sys
import uuid
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

def test_conversation():
    """Test the conversation API integration"""
    try:
        # Initialize SDK
        keychain = Keychain("United States", None)
        chariot = Chariot(keychain=keychain, proxy="")
        
        print(f"Base URL: {keychain.base_url()}")
        print(f"Username: {keychain.username()}")
        
        # Test conversation API call
        url = chariot.url("/conversations")
        conversation_id = str(uuid.uuid4())
        
        payload = {
            "conversationId": conversation_id,
            "message": "Hello, this is a test message"
        }
        
        print(f"Testing API call to: {url}")
        print(f"Payload: {payload}")
        
        response = chariot._make_request("POST", url, json=payload)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Parsed response: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_conversation()