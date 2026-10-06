from types import SimpleNamespace
from unittest.mock import patch

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
