import json
import os
from time import sleep, time
import asyncio

from praetorian_cli.sdk.model.globals import AgentType
from praetorian_cli.sdk.mcp_server import MCPServer


class Agents:

    def __init__(self, api):
        self.api = api
        self._conversation_id = None

    def affiliation(self, key, timeout=180) -> str:
        self.api.agent(AgentType.AFFILIATION.value, dict(key=key))

        # poll for the affiliation job to complete
        job_key = self.api.jobs.system_job_key(AgentType.AFFILIATION.value, key)

        start_time = time()
        while time() - start_time < timeout:
            job = self.api.jobs.get(job_key)
            if self.api.jobs.is_failed(job):
                raise Exception('Failed to retrieve affiliation data.')
            if self.api.jobs.is_passed(job):
                break
            sleep(1)

        if self.api.jobs.is_passed(job):
            return self.affiliation_result(key)
        else:
            raise Exception(f'Timeout waiting for affiliation result ({timeout} seconds).')

    def affiliation_filename(self, agent_type: str, key: str) -> str:
        return f'agents/{agent_type}/{key}'

    def affiliation_result(self, key: str) -> dict:
        return self.api.files.get_utf8(self.affiliation_filename(AgentType.AFFILIATION.value, key))

    def ask(self, message, mode='agent', conversation_id=None, new=False, timeout=180):
        """
        Send a message to the Guard AI assistant and poll for the response.

        Returns a dict with 'response' (str), 'conversation_id' (str), and
        'tool_calls' (list of dicts with role/content for intermediate messages).

        :param message: The message to send
        :type message: str
        :param mode: Conversation mode ('query' or 'agent')
        :type mode: str
        :param conversation_id: Existing conversation ID to continue, or None for new
        :type conversation_id: str or None
        :param new: Force a new conversation even if conversation_id is set
        :type new: bool
        :param timeout: Maximum seconds to wait for response
        :type timeout: int
        :return: Dict with response, conversation_id, and tool_calls
        :rtype: dict
        """
        if new:
            conversation_id = None
        elif conversation_id is None:
            conversation_id = self._conversation_id

        url = self.api.url('/planner')
        payload = {'message': message, 'mode': mode}
        if conversation_id:
            payload['conversationId'] = conversation_id

        response = self.api.chariot_request('POST', url, json=payload)
        if not response.ok:
            raise Exception(f'[{response.status_code}] {response.text}')

        result = response.json()
        if not conversation_id and 'conversation' in result:
            conversation_id = result['conversation'].get('uuid')
        self._conversation_id = conversation_id

        # Snapshot existing messages so we only process new ones
        last_key = ''
        try:
            existing, _ = self.api.search.by_key_prefix(
                f'#message#{conversation_id}#', user=True
            )
            if existing:
                last_key = max(m.get('key', '') for m in existing)
        except Exception:
            pass

        # Poll for AI response
        start_time = time()
        tool_calls = []

        while time() - start_time < timeout:
            try:
                messages, _ = self.api.search.by_key_prefix(
                    f'#message#{conversation_id}#', user=True
                )
                new_msgs = sorted(
                    [m for m in messages if m.get('key', '') > last_key],
                    key=lambda x: x.get('key', '')
                )
                for msg in new_msgs:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    last_key = msg.get('key', '')

                    if role == 'chariot':
                        return {
                            'response': content,
                            'conversation_id': conversation_id,
                            'tool_calls': tool_calls,
                        }
                    elif role in ('tool call', 'tool response'):
                        tool_calls.append({'role': role, 'content': content})
            except Exception:
                pass
            sleep(1)

        raise Exception(f'Timeout waiting for AI response ({timeout}s)')

    @property
    def conversation_id(self):
        """Current conversation ID for follow-up messages."""
        return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, value):
        self._conversation_id = value

    def send(self, message, agent='research-coordinator', mode='agent'):
        """Start a conversation without polling to completion.

        Returns a dict with 'conversation_id' and optionally 'response' if the
        backend returned an immediate result.

        :param message: The message to send
        :type message: str
        :param agent: The agent to address (used as context in the message)
        :type agent: str
        :param mode: Conversation mode ('query' or 'agent')
        :type mode: str
        :return: Dict with conversation_id (and response if immediately available)
        :rtype: dict
        """
        url = self.api.url('/planner')
        payload = {
            'message': f'[agent:{agent}] {message}',
            'mode': mode,
        }

        response = self.api.chariot_request('POST', url, json=payload)
        if not response.ok:
            raise Exception(f'[{response.status_code}] {response.text}')

        result = response.json()
        conversation_id = None
        if 'conversation' in result:
            conversation_id = result['conversation'].get('uuid')

        if conversation_id:
            self._conversation_id = conversation_id

        return {
            'conversation_id': conversation_id,
            'response': result.get('response', ''),
            'id': conversation_id or '',
        }

    def poll(self, conversation_id):
        """Poll for the current state of a conversation.

        Returns a dict with 'response' (accumulated text), 'status' (e.g.
        'pending', 'complete', 'error'), and optionally 'error'.

        :param conversation_id: The conversation to poll
        :type conversation_id: str
        :return: Dict with response, status, and optional error
        :rtype: dict
        """
        try:
            messages, _ = self.api.search.by_key_prefix(
                f'#message#{conversation_id}#', user=True
            )
            sorted_msgs = sorted(messages, key=lambda x: x.get('key', ''))

            response_parts = []
            status = 'pending'

            for msg in sorted_msgs:
                role = msg.get('role', '')
                content = msg.get('content', '')

                if role == 'chariot':
                    response_parts.append(content)
                    status = 'complete'
                elif role in ('tool call', 'tool response'):
                    # Include tool progress in response stream
                    pass

            return {
                'response': '\n'.join(response_parts),
                'status': status,
            }
        except Exception as e:
            return {
                'response': '',
                'status': 'error',
                'error': str(e),
            }

    def start_mcp_server(self, allowable_tools=None):
        server = MCPServer(self.api, allowable_tools)
        return asyncio.run(server.start())

    def list_mcp_tools(self, allowable_tools=None):
        server = MCPServer(self.api, allowable_tools)
        return server.discovered_tools
