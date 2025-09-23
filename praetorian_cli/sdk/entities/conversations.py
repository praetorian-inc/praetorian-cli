import json
import uuid
from datetime import datetime


class Conversations:
    """ The methods in this class are to be assessed from sdk.conversations, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api

    def send_message(self, conversation_id, message, username=None):
        """
        Send a message to a planner conversation and get a response.

        This method interfaces with the planner service to send a user message
        and receive an AI-generated response. The planner can execute security
        tools and provide intelligent analysis of the results.

        :param conversation_id: ID of the conversation to send the message to
        :type conversation_id: str
        :param message: The user message to send to the planner
        :type message: str
        :param username: Username for the message (uses keychain if not provided)
        :type username: str or None
        :return: Planner response with conversation details
        :rtype: dict

        **Example Usage:**
            >>> # Start a new conversation
            >>> response = sdk.conversations.send_message(
            >>>     "550e8400-e29b-41d4-a716-446655440000",
            >>>     "Show me all critical vulnerabilities on example.com"
            >>> )

            >>> # Continue an existing conversation
            >>> response = sdk.conversations.send_message(
            >>>     "550e8400-e29b-41d4-a716-446655440000",
            >>>     "Run a port scan on that server"
            >>> )

        **Response Structure:**
            The returned response contains:
            - content: AI response text
            - conversationId: The conversation ID
            - timestamp: Response timestamp
            - toolsUsed: List of tools executed (if any)
        """
        if not username:
            username = self.api.keychain.username

        data = {
            'conversationId': conversation_id,
            'userMessage': message,
            'username': username
        }

        response = self.api.post('planner/ProcessPlanner', data)
        return response

    def list_messages(self, conversation_id, offset=None, pages=100000) -> tuple:
        """
        List messages in a conversation.

        Retrieve all messages from a conversation, including user messages,
        AI responses, tool calls, and tool results.

        :param conversation_id: ID of the conversation to retrieve messages from
        :type conversation_id: str
        :param offset: The offset for pagination to retrieve a specific page
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: A tuple containing (list of messages, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # Get all messages from a conversation
            >>> messages, offset = sdk.conversations.list_messages(
            >>>     "550e8400-e29b-41d4-a716-446655440000"
            >>> )

        **Message Structure:**
            Each message contains:
            - messageId: Unique message identifier
            - conversationId: Parent conversation ID
            - role: Message role (user, chariot, system, tool call, tool response)
            - content: Message content
            - timestamp: Message timestamp
            - username: Message author
        """
        prefix_filter = f"#message#{conversation_id}"
        return self.api.search.by_key_prefix(prefix_filter, offset, pages)

    def list_conversations(self, username=None, offset=None, pages=100000) -> tuple:
        """
        List conversations for a user.

        Retrieve all conversations created by or involving a specific user.

        :param username: Username to filter conversations (uses keychain if not provided)
        :type username: str or None
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: A tuple containing (list of conversations, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all conversations for current user
            >>> conversations, offset = sdk.conversations.list_conversations()

            >>> # List conversations for specific user
            >>> conversations, offset = sdk.conversations.list_conversations("user@example.com")

        **Conversation Structure:**
            Each conversation contains:
            - uuid: Conversation identifier
            - source: Who started the conversation
            - created: Creation timestamp
            - updated: Last update timestamp
        """
        if not username:
            username = self.api.keychain.username

        # Search for conversations by user
        prefix_filter = f"#conversation#{username}"
        return self.api.search.by_key_prefix(prefix_filter, offset, pages)

    def get_conversation(self, conversation_id):
        """
        Get details of a specific conversation.

        :param conversation_id: The conversation ID to retrieve
        :type conversation_id: str
        :return: Conversation object or None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> conversation = sdk.conversations.get_conversation(
            >>>     "550e8400-e29b-41d4-a716-446655440000"
            >>> )
        """
        key = f"#conversation#{conversation_id}"
        return self.api.search.by_exact_key(key)

    def create_conversation(self, username=None):
        """
        Create a new conversation.

        :param username: Username for the conversation owner (uses keychain if not provided)
        :type username: str or None
        :return: New conversation object
        :rtype: dict

        **Example Usage:**
            >>> conversation = sdk.conversations.create_conversation()
            >>> conversation_id = conversation['uuid']
        """
        if not username:
            username = self.api.keychain.username

        conversation_id = str(uuid.uuid4())
        
        # Create conversation by sending an initial system message
        # This will trigger conversation creation in the planner service
        data = {
            'conversationId': conversation_id,
            'userMessage': 'Hello', # Initial message to create conversation
            'username': username
        }

        response = self.api.post('planner/ProcessPlanner', data)
        
        # Return the conversation details
        return {
            'uuid': conversation_id,
            'source': username,
            'created': datetime.now().isoformat(),
            'response': response
        }

    def get_conversation_jobs(self, conversation_id):
        """
        Get jobs associated with a conversation.

        Retrieve all security scanning jobs that were initiated from
        within a conversation context.

        :param conversation_id: The conversation ID
        :type conversation_id: str
        :return: List of job objects
        :rtype: list

        **Example Usage:**
            >>> jobs = sdk.conversations.get_conversation_jobs(
            >>>     "550e8400-e29b-41d4-a716-446655440000"
            >>> )
        """
        data = {
            'conversationId': conversation_id
        }
        
        response = self.api.post('planner/GetConversationJobs', data)
        return response.get('jobs', [])