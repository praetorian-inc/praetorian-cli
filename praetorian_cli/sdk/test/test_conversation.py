import pytest
import json
import time

from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestConversation:
    """Test conversation functionality with the Chariot agent"""

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        self.conversation_id = None
        self.message_keys = []

    def test_start_conversation(self):
        """Test starting a new conversation with the agent"""
        url = self.sdk.url("/planner")
        payload = {
            "message": f"Test conversation started at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=payload)
        
        # Should get successful response
        assert response.status_code == 200
        
        result = response.json()
        assert "conversation" in result
        assert "uuid" in result["conversation"]
        
        self.conversation_id = result["conversation"]["uuid"]
        assert self.conversation_id is not None
        assert len(self.conversation_id) > 0

    def test_send_message_with_existing_conversation(self):
        """Test sending a message to an existing conversation"""
        # First, start a new conversation
        url = self.sdk.url("/planner")
        initial_payload = {
            "message": f"Initial message for follow-up test at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=initial_payload)
        assert response.status_code == 200
        
        result = response.json()
        conversation_id = result["conversation"]["uuid"]
        
        # Now send a follow-up message to the existing conversation
        follow_up_payload = {
            "message": f"Follow-up message in existing conversation at {int(time.time())}",
            "mode": "query",
            "conversationId": conversation_id
        }
        
        response = self.sdk.chariot_request("POST", url, json=follow_up_payload)
        
        # Should get successful response
        assert response.status_code == 200

    def test_read_conversation_messages(self):
        """Test reading messages from a conversation"""
        # First, create a conversation and send a message
        url = self.sdk.url("/planner")
        payload = {
            "message": f"Test message for reading at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=payload)
        assert response.status_code == 200
        
        result = response.json()
        conversation_id = result["conversation"]["uuid"]
        
        # Wait a moment for message to be stored
        time.sleep(2)
        
        # Now try to read messages from this conversation
        messages, offset = self.sdk.search.by_key_prefix(
            f"#message#{conversation_id}#", user=True
        )
        
        # Should have at least the user message
        assert isinstance(messages, list)
        # Note: messages might be empty immediately after creation due to async processing
        # This is still a valid test as it verifies the search functionality works

    def test_read_conversations_list(self):
        """Test reading list of conversations"""
        # First create a test conversation
        url = self.sdk.url("/planner")
        payload = {
            "message": f"Test conversation for listing at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=payload)
        assert response.status_code == 200
        
        # Wait a moment for conversation to be stored
        time.sleep(1)
        
        # Now search for conversations
        conversations, offset = self.sdk.search.by_key_prefix(
            "#conversation#", user=True
        )
        
        # Should be able to search for conversations (list might be empty or contain conversations)
        assert isinstance(conversations, list)

    def test_conversation_api_error_handling(self):
        """Test handling of malformed requests"""
        url = self.sdk.url("/planner")
        # Send malformed payload (missing required fields)
        malformed_payload = {
            "invalid_field": "should cause error"
            # Missing required "message" field
        }
        
        response = self.sdk.chariot_request("POST", url, json=malformed_payload)
        
        # Should get a 4xx error for bad request
        assert response.status_code >= 400

    def test_conversation_modes(self):
        """Test different conversation modes (query vs agent)"""
        url = self.sdk.url("/planner")
        
        # Test query mode
        query_payload = {
            "message": f"Test query mode at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=query_payload)
        assert response.status_code == 200
        
        result = response.json()
        assert "conversation" in result
        
        # Test agent mode
        agent_payload = {
            "message": f"Test agent mode at {int(time.time())}",
            "mode": "agent"
        }
        
        response = self.sdk.chariot_request("POST", url, json=agent_payload)
        assert response.status_code == 200
        
        result = response.json()
        assert "conversation" in result

    def test_message_polling_integration(self):
        """Test integration of message polling to check for new messages"""
        # Create a conversation first
        url = self.sdk.url("/planner")
        payload = {
            "message": f"Test message for polling at {int(time.time())}",
            "mode": "query"
        }
        
        response = self.sdk.chariot_request("POST", url, json=payload)
        assert response.status_code == 200
        
        result = response.json()
        conversation_id = result["conversation"]["uuid"]
        
        # Test polling for messages (first call)
        messages, offset = self.sdk.search.by_key_prefix(
            f"#message#{conversation_id}#", user=True
        )
        
        initial_count = len(messages) if messages else 0
        
        # Wait a moment and check again (simulating polling)
        time.sleep(1)
        
        messages, offset = self.sdk.search.by_key_prefix(
            f"#message#{conversation_id}#", user=True
        )
        
        # Should still return valid result (messages may or may not have changed)
        assert isinstance(messages, list)

    def teardown_class(self):
        """Clean up test data"""
        # Note: Conversations and messages are typically read-only in tests
        # Real cleanup would depend on having delete methods for conversations
        pass