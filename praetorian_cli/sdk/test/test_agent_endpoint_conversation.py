import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.agent import agent
from praetorian_cli.sdk.model.aegis import Agent
from praetorian_cli.ui.conversation.textual_chat import ConversationApp


ENDPOINT_ID = '11111111-1111-4111-8111-111111111111'


class FakeAegis:
    def __init__(self, endpoints):
        self.endpoints = endpoints

    def list_hunt_endpoints(self):
        return list(self.endpoints)


def _endpoint(hostname='aegis-internal'):
    return Agent.from_endpoint_dict({
        'endpointId': ENDPOINT_ID,
        'hostname': hostname,
        'online': False,
    })


@pytest.mark.parametrize('endpoint_ref', ['', ' ', '\t'])
@pytest.mark.parametrize('confirmed', [False, True])
def test_agent_conversation_rejects_blank_endpoint(endpoint_ref, confirmed):
    sdk = SimpleNamespace()
    arguments = ['conversation', '--mode', 'agent', '--endpoint', endpoint_ref]
    if confirmed:
        arguments.append('--confirm-endpoint')

    with patch('praetorian_cli.ui.conversation.run_textual_conversation') as run:
        result = CliRunner().invoke(agent, arguments, obj=sdk)

    assert result.exit_code == 2, result.output
    assert 'Endpoint reference cannot be empty' in result.output
    run.assert_not_called()


def test_agent_conversation_without_endpoint_remains_unbound():
    sdk = SimpleNamespace()

    with patch('praetorian_cli.ui.conversation.run_textual_conversation') as run:
        result = CliRunner().invoke(agent, ['conversation'], obj=sdk)

    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        sdk, mode='query', endpoint_id=None, endpoint_confirmed=False,
    )


def test_agent_conversation_binds_confirmed_endpoint():
    sdk = SimpleNamespace(aegis=FakeAegis([_endpoint()]))

    with patch(
        'praetorian_cli.ui.conversation.run_textual_conversation'
    ) as run:
        result = CliRunner().invoke(
            agent,
            [
                'conversation', '--mode', 'agent', '--endpoint', ENDPOINT_ID,
                '--confirm-endpoint',
            ],
            obj=sdk,
        )

    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        sdk,
        mode='agent',
        endpoint_id=ENDPOINT_ID,
        endpoint_confirmed=True,
    )


def test_agent_conversation_confirmation_names_offline_no_fallback_policy():
    sdk = SimpleNamespace(aegis=FakeAegis([_endpoint()]))

    with patch('praetorian_cli.ui.conversation.run_textual_conversation'):
        result = CliRunner().invoke(
            agent,
            ['conversation', '--mode', 'agent', '--endpoint', 'aegis-internal'],
            obj=sdk,
            input='y\n',
        )

    assert result.exit_code == 0, result.output
    assert 'aegis-internal' in result.output
    assert ENDPOINT_ID in result.output
    assert 'offline' in result.output
    assert 'will not fall back to Guard compute' in result.output


def test_agent_conversation_endpoint_requires_agent_mode():
    sdk = SimpleNamespace(aegis=FakeAegis([_endpoint()]))

    result = CliRunner().invoke(
        agent,
        ['conversation', '--mode', 'query', '--endpoint', ENDPOINT_ID],
        obj=sdk,
    )

    assert result.exit_code != 0
    assert '--endpoint requires --mode agent' in result.output


class FakePlannerResponse:
    status_code = 200
    text = ''

    def json(self):
        return {'conversation': {'uuid': 'conversation-1'}}


class FakeConversationSDK:
    def __init__(self):
        self.payloads = []

    def get_current_user(self):
        return 'user@example.com', 'user'

    def url(self, path):
        assert path == '/planner'
        return path

    def chariot_request(self, method, url, json):
        assert (method, url) == ('POST', '/planner')
        self.payloads.append(dict(json))
        return FakePlannerResponse()


def test_textual_endpoint_conversation_sends_placement_only_on_creation():
    sdk = FakeConversationSDK()
    app = ConversationApp(
        sdk,
        mode='agent',
        endpoint_id=ENDPOINT_ID,
        endpoint_confirmed=True,
    )
    app.update_status = lambda _status: None

    assert app.call_conversation_api('start') == {'success': True}
    assert sdk.payloads == [{
        'message': 'start',
        'mode': 'agent',
        'endpointRequired': True,
        'endpointId': ENDPOINT_ID,
        'endpointConfirmed': True,
    }]

    app.call_conversation_api('follow up')

    assert sdk.payloads[1] == {
        'message': 'follow up',
        'mode': 'agent',
        'conversationId': 'conversation-1',
    }


def _resume_app(selected, root=None):
    sdk = FakeConversationSDK()
    sdk.conversations = SimpleNamespace(
        root_id=Mock(return_value=(root or selected)['uuid']),
        get_metadata=Mock(return_value=root or selected),
    )
    app = ConversationApp(sdk)
    app._available_conversations = [selected]
    app._selecting_conversation = True
    app.clear_chat = AsyncMock()
    app.load_conversation_history = AsyncMock()
    app._restore_message_input = Mock()
    app.add_system_message = Mock()
    app.update_status = Mock()
    return app


def _pinned_conversation():
    return {
        'uuid': 'conversation-1',
        'endpointRequired': True,
        'endpointId': ENDPOINT_ID,
    }


@pytest.mark.parametrize('resume_child', [False, True])
def test_resume_restores_endpoint_from_root_and_sends_agent_followup(resume_child):
    root = _pinned_conversation()
    selected = {'uuid': 'child-1'} if resume_child else root
    app = _resume_app(selected, root)

    asyncio.run(app.handle_conversation_selection('1'))

    assert app.conversation_id == selected['uuid']
    assert app.root_conversation_id == root['uuid']
    assert app.endpoint_id == ENDPOINT_ID
    assert app.mode == 'agent'
    app.set_mode('query')
    assert app.mode == 'agent'
    app.call_conversation_api('continue')
    assert app.sdk.payloads == [{
        'message': 'continue',
        'mode': 'agent',
        'conversationId': selected['uuid'],
    }]


def test_new_after_resume_does_not_copy_endpoint_placement():
    app = _resume_app(_pinned_conversation())
    asyncio.run(app.handle_conversation_selection('1'))

    asyncio.run(app.start_new_conversation())

    assert app.endpoint_id is None
    assert app.endpoint_confirmed is False
    app.call_conversation_api('new conversation')
    assert app.sdk.payloads == [{
        'message': 'new conversation', 'mode': 'agent',
    }]


def test_resume_can_switch_from_pinned_to_unbound_conversation():
    app = _resume_app(_pinned_conversation())
    asyncio.run(app.handle_conversation_selection('1'))
    unbound = {'uuid': 'conversation-2', 'created': '2026-01-01'}
    app.sdk.search = SimpleNamespace(by_key_prefix=Mock(return_value=([unbound], None)))
    app.sdk.conversations.root_id.return_value = unbound['uuid']

    asyncio.run(app.resume_conversation())
    assert app._selecting_conversation is True
    asyncio.run(app.handle_conversation_selection('1'))

    assert app.endpoint_id is None
    assert app.endpoint_confirmed is False
    app.set_mode('query')
    assert app.mode == 'query'
    app.call_conversation_api('query')
    assert app.sdk.payloads == [{
        'message': 'query', 'mode': 'query', 'conversationId': 'conversation-2',
    }]


@pytest.mark.parametrize('failure', ['root_lookup', 'root_metadata', 'missing_endpoint'])
def test_resume_does_not_switch_when_placement_cannot_be_restored(failure):
    root = _pinned_conversation()
    app = _resume_app({'uuid': 'child-1'}, root)
    app.conversation_id = 'previous-conversation'
    if failure == 'root_lookup':
        app.sdk.conversations.root_id.side_effect = RuntimeError('unavailable')
    elif failure == 'root_metadata':
        app.sdk.conversations.get_metadata.side_effect = RuntimeError('unavailable')
    else:
        root.pop('endpointId')

    asyncio.run(app.handle_conversation_selection('1'))

    assert app.conversation_id == 'previous-conversation'
    assert app._selecting_conversation is True
    app.load_conversation_history.assert_not_awaited()
    assert 'Unable to restore conversation placement' in app.add_system_message.call_args.args[0]


def test_explicit_endpoint_session_still_rejects_resume_and_keeps_new_placement():
    app = ConversationApp(
        FakeConversationSDK(), mode='agent',
        endpoint_id=ENDPOINT_ID, endpoint_confirmed=True,
    )
    app.add_system_message = Mock()
    app.clear_chat = AsyncMock()
    app.update_status = Mock()
    app._restore_message_input = Mock()

    asyncio.run(app.resume_conversation())
    assert app._selecting_conversation is False
    assert 'Endpoint placement is immutable' in app.add_system_message.call_args.args[0]
    asyncio.run(app.start_new_conversation())
    app.call_conversation_api('start')
    assert app.sdk.payloads[0]['endpointId'] == ENDPOINT_ID
    assert app.sdk.payloads[0]['endpointConfirmed'] is True
