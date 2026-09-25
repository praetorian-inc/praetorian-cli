import pytest

from praetorian_cli.sdk.entities import agents as agents_module
from praetorian_cli.sdk.entities.agents import Agents


class FakeResponse:
    ok = True
    status_code = 200
    text = ''

    def json(self):
        return {'conversation': {'uuid': 'conversation-1'}}


class FakeSearch:
    def __init__(self, complete_after=3):
        self.calls = 0
        self.complete_after = complete_after

    def by_key_prefix(self, key, user=False):
        assert key == '#message#conversation-1#'
        assert user is True
        self.calls += 1
        if self.calls < self.complete_after:
            return [], None
        return [{
            'key': '#message#conversation-1#2',
            'role': 'chariot',
            'content': 'done',
        }], None


class FakeConversations:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def list_interactions(
        self, conversation_id, status=None, include_descendants=False
    ):
        assert conversation_id == 'conversation-1'
        assert status == 'pending'
        assert include_descendants is True
        self.calls += 1
        if self.error:
            raise self.error
        return [{
            'conversationId': conversation_id,
            'requestId': 'request-1',
            'kind': 'approval',
            'status': 'pending',
        }]


class FakeEndpointExecutions:
    def __init__(self):
        self.status = {'sessions': [], 'tasks': []}
        self.calls = []

    def conversation_status(self, conversation_id):
        self.calls.append(conversation_id)
        return self.status


class FakeAPI:
    def __init__(self, interaction_error=None, complete_after=3):
        self.search = FakeSearch(complete_after)
        self.conversations = FakeConversations(interaction_error)
        self.endpoint_executions = FakeEndpointExecutions()

    def url(self, path):
        assert path == '/planner'
        return path

    def chariot_request(self, method, url, json):
        assert (method, url) == ('POST', '/planner')
        assert json == {'message': 'test', 'mode': 'agent'}
        return FakeResponse()


def test_ask_delivers_each_pending_interaction_once(monkeypatch):
    monkeypatch.setattr(agents_module, 'sleep', lambda _seconds: None)
    api = FakeAPI()
    handled = []

    result = Agents(api).ask('test', interaction_handler=handled.append)

    assert result['response'] == 'done'
    assert [interaction['requestId'] for interaction in handled] == ['request-1']
    assert api.conversations.calls == 1


def test_ask_excludes_operator_prompt_time_from_timeout(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(agents_module, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(agents_module, 'sleep', lambda _seconds: None)

    def handle(_interaction):
        clock[0] += 2

    result = Agents(FakeAPI()).ask(
        'test',
        timeout=1,
        interaction_handler=handle,
    )

    assert result['response'] == 'done'


def test_pending_interaction_delivery_is_deduplicated():
    api = FakeAPI()
    agent = Agents(api)
    handled_ids = set()
    delivered = []

    agent._handle_pending_interactions(
        'conversation-1', delivered.append, handled_ids
    )
    agent._handle_pending_interactions(
        'conversation-1', delivered.append, handled_ids
    )

    assert [interaction['requestId'] for interaction in delivered] == ['request-1']
    assert api.conversations.calls == 2


def test_endpoint_status_handler_receives_only_changed_nonempty_status():
    api = FakeAPI()
    api.endpoint_executions.status = {
        'sessions': [{
            'sessionId': 'session-1',
            'state': 'Ready',
            'activeOperations': [{
                'operationId': 'operation-1',
                'state': 'Running',
                'stdout': 'first chunk',
            }],
        }],
        'tasks': [],
    }
    agent = Agents(api)
    delivered = []

    fingerprint = agent._handle_endpoint_status(
        'conversation-1', delivered.append, None
    )
    api.endpoint_executions.status['sessions'][0]['activeOperations'][0][
        'stdout'
    ] = 'second chunk'
    same = agent._handle_endpoint_status(
        'conversation-1', delivered.append, fingerprint
    )

    assert len(delivered) == 1
    assert delivered[0]['sessions'][0]['sessionId'] == 'session-1'
    assert same == fingerprint


def test_endpoint_status_handlers_allow_missing_sessions_or_tasks():
    api = FakeAPI()
    agent = Agents(api)
    delivered = []

    for status in ({'sessions': []}, {'tasks': []}, {}):
        api.endpoint_executions.status = status
        agent._handle_endpoint_status('conversation-1', delivered.append, None)

    assert delivered == []


def test_poll_allows_missing_endpoint_status_keys():
    api = FakeAPI()
    api.endpoint_executions.status = {'sessions': []}

    result = Agents(api).poll('conversation-1')

    assert result['status'] == 'pending'
    assert 'error' not in result


def test_ask_checks_for_completed_response_before_endpoint_status(monkeypatch):
    monkeypatch.setattr(agents_module, 'sleep', lambda _seconds: None)
    api = FakeAPI(complete_after=2)

    result = Agents(api).ask(
        'test',
        endpoint_status_handler=lambda _status: None,
    )

    assert result['response'] == 'done'
    assert api.endpoint_executions.calls == []


def test_ask_preserves_existing_behavior_without_interaction_handler(monkeypatch):
    monkeypatch.setattr(agents_module, 'sleep', lambda _seconds: None)
    api = FakeAPI()

    result = Agents(api).ask('test')

    assert result['response'] == 'done'
    assert api.conversations.calls == 0


def test_ask_retries_interaction_reads_but_does_not_hide_handler_failures(monkeypatch):
    monkeypatch.setattr(agents_module, 'sleep', lambda _seconds: None)
    api = FakeAPI(interaction_error=RuntimeError('temporary read failure'))

    result = Agents(api).ask('test', interaction_handler=lambda _row: None)

    assert result['response'] == 'done'
    assert api.conversations.calls == 1

    api = FakeAPI()

    def fail(_interaction):
        raise RuntimeError('operator prompt failed')

    with pytest.raises(RuntimeError, match='operator prompt failed'):
        Agents(api).ask('test', interaction_handler=fail)
