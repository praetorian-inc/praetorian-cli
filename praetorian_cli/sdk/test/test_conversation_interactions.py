import pytest

from praetorian_cli.sdk.entities.conversations import Conversations


class FakeAPI:
    def __init__(self, interactions=None, *, my_error=None, post_error=None):
        self.interactions = interactions or []
        self.my_error = my_error
        self.post_error = post_error
        self.my_calls = []
        self.post_calls = []

    def my(self, params, pages=1):
        self.my_calls.append({'params': dict(params), 'pages': pages})
        if self.my_error:
            raise self.my_error
        return {'interactions': list(self.interactions), 'offset': {'key': 'next'}}

    def post(self, path, body):
        self.post_calls.append({'path': path, 'body': dict(body)})
        if self.post_error:
            raise self.post_error
        return {'status': 'answered'}


def test_list_interactions_routes_through_conversation_partition_and_sorts():
    api = FakeAPI([
        {'key': '#interaction#conversation-1#2', 'kind': 'future-kind', 'status': 'pending'},
        {'key': '#interaction#conversation-1#1', 'kind': 'approval', 'status': 'answered'},
    ])

    interactions = Conversations(api).list_interactions(' conversation-1 ')

    assert [interaction['key'] for interaction in interactions] == [
        '#interaction#conversation-1#1',
        '#interaction#conversation-1#2',
    ]
    assert interactions[1]['kind'] == 'future-kind'
    assert api.my_calls == [{
        'params': {
            'key': '#interaction#conversation-1#',
            'convId': 'conversation-1',
        },
        'pages': 100000,
    }]


def test_list_interactions_filters_by_status_without_filtering_kind():
    api = FakeAPI([
        {'key': '#interaction#conversation-1#1', 'kind': 'approval', 'status': 'pending'},
        {'key': '#interaction#conversation-1#2', 'kind': 'future-kind', 'status': 'pending'},
        {'key': '#interaction#conversation-1#3', 'kind': 'credential', 'status': 'expired'},
    ])

    interactions = Conversations(api).list_interactions('conversation-1', status=' pending ')

    assert [interaction['kind'] for interaction in interactions] == ['approval', 'future-kind']


def test_answer_interaction_posts_exact_guard_contract_and_preserves_response():
    api = FakeAPI()

    result = Conversations(api).answer_interaction(
        ' conversation-1 ', ' request-1 ', ' true '
    )

    assert result == {'status': 'answered'}
    assert api.post_calls == [{
        'path': 'planner/interaction',
        'body': {
            'conversationId': 'conversation-1',
            'requestId': 'request-1',
            'response': ' true ',
        },
    }]


@pytest.mark.parametrize(
    ('method', 'args', 'message'),
    [
        ('list_interactions', ('  ',), 'conversation ID is required'),
        ('list_interactions', ('conversation-1', '  '), 'interaction status is required'),
        ('answer_interaction', ('  ', 'request-1', 'true'), 'conversation ID is required'),
        ('answer_interaction', ('conversation-1', '  ', 'true'), 'request ID is required'),
        ('answer_interaction', ('conversation-1', 'request-1', '  '), 'interaction response is required'),
        ('answer_interaction', ('conversation-1', 'request-1', False), 'interaction response is required'),
    ],
)
def test_interaction_methods_validate_before_request(method, args, message):
    api = FakeAPI()

    with pytest.raises(ValueError, match=message):
        getattr(Conversations(api), method)(*args)

    assert api.my_calls == []
    assert api.post_calls == []


def test_list_interactions_propagates_api_failures():
    failure = RuntimeError('search failed')

    with pytest.raises(RuntimeError, match='search failed'):
        Conversations(FakeAPI(my_error=failure)).list_interactions('conversation-1')


def test_answer_interaction_propagates_api_failures():
    failure = RuntimeError('[409] interaction already answered')

    with pytest.raises(RuntimeError, match='interaction already answered'):
        Conversations(FakeAPI(post_error=failure)).answer_interaction(
            'conversation-1', 'request-1', 'false'
        )
