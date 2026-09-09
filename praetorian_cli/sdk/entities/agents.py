import os
from time import monotonic, sleep, time
import asyncio

from praetorian_cli.sdk.entities.endpoint_executions import (
    endpoint_status_fingerprint,
)
from praetorian_cli.sdk.model.globals import AgentType
from praetorian_cli.sdk.mcp_server import MCPServer


INTERACTION_POLL_INTERVAL_SECONDS = 5
ENDPOINT_STATUS_POLL_INTERVAL_SECONDS = 3


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

    def ask(self, message, mode='agent', conversation_id=None, new=False,
            timeout=180, interaction_handler=None, endpoint_status_handler=None):
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
        :param interaction_handler: Optional callback for each pending interaction
        :type interaction_handler: callable or None
        :param endpoint_status_handler: Optional callback for endpoint status changes
        :type endpoint_status_handler: callable or None
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
        deadline = monotonic() + timeout
        tool_calls = []
        handled_interactions = set()
        next_interaction_poll = monotonic()
        next_endpoint_status_poll = monotonic()
        last_endpoint_status = None

        while monotonic() < deadline:
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

            now = monotonic()
            if interaction_handler and now >= next_interaction_poll:
                interaction_started = monotonic()
                self._handle_pending_interactions(
                    conversation_id,
                    interaction_handler,
                    handled_interactions,
                )
                interaction_finished = monotonic()
                deadline += interaction_finished - interaction_started
                next_interaction_poll = (
                    interaction_finished + INTERACTION_POLL_INTERVAL_SECONDS
                )

            now = monotonic()
            if endpoint_status_handler and now >= next_endpoint_status_poll:
                last_endpoint_status = self._handle_endpoint_status(
                    conversation_id,
                    endpoint_status_handler,
                    last_endpoint_status,
                )
                next_endpoint_status_poll = (
                    monotonic() + ENDPOINT_STATUS_POLL_INTERVAL_SECONDS
                )
            sleep(1)

        raise Exception(f'Timeout waiting for AI response ({timeout}s)')

    def _handle_pending_interactions(self, conversation_id, handler, handled):
        try:
            interactions = self.api.conversations.list_interactions(
                conversation_id,
                status='pending',
                include_descendants=True,
            )
        except Exception:
            return

        for interaction in interactions:
            request_id = interaction.get('requestId')
            if not request_id or request_id in handled:
                continue
            handled.add(request_id)
            handler(interaction)

    def _handle_endpoint_status(self, conversation_id, handler, previous):
        try:
            status = self.api.endpoint_executions.conversation_status(
                conversation_id
            )
        except Exception:
            return previous
        fingerprint = endpoint_status_fingerprint(status)
        if fingerprint != previous and (status['sessions'] or status['tasks']):
            handler(status)
        return fingerprint

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

            result = {
                'response': '\n'.join(response_parts),
                'status': status,
            }
            try:
                endpoint_status = self.api.endpoint_executions.conversation_status(
                    conversation_id
                )
            except Exception:
                endpoint_status = None
            if endpoint_status and (
                endpoint_status['sessions'] or endpoint_status['tasks']
            ):
                result['endpoint_execution'] = endpoint_status
            return result
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
