import pytest

from praetorian_cli.sdk.entities.aegis import Aegis


class FakeAPI:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def get(self, path):
        self.calls.append({'method': 'GET', 'path': path})
        return self.responses.get(path, {'ok': True})

    def post(self, path, body):
        self.calls.append({'method': 'POST', 'path': path, 'body': body})
        return self.responses.get(path, {'ok': True})


def test_get_cloudflare_tunnel_status_uses_encoded_endpoint_uuid():
    response = {
        'configuration': {'state': 'configured'},
        'runtime': {'state': 'running', 'reason': 'ready'},
    }
    api = FakeAPI({
        'aegis/management/cloudflare/tunnel/status/endpoint%2Fone': response,
    })

    result = Aegis(api).get_cloudflare_tunnel_status(' endpoint/one ')

    assert result == response
    assert api.calls == [{
        'method': 'GET',
        'path': 'aegis/management/cloudflare/tunnel/status/endpoint%2Fone',
    }]


def test_create_cloudflare_tunnel_posts_endpoint_uuid_only():
    api = FakeAPI({'aegis/management/cloudflare/tunnel/create': {'installTaskId': 'task-1'}})

    result = Aegis(api).create_cloudflare_tunnel(' endpoint-1 ')

    assert result == {'installTaskId': 'task-1'}
    assert api.calls == [{
        'method': 'POST',
        'path': 'aegis/management/cloudflare/tunnel/create',
        'body': {'endpointAgentId': 'endpoint-1'},
    }]
    assert 'aegisClientId' not in api.calls[0]['body']


def test_create_cloudflare_tunnel_posts_legacy_client_id():
    api = FakeAPI()

    Aegis(api).create_cloudflare_tunnel(' C.legacy ', legacy=True)

    assert api.calls == [{
        'method': 'POST',
        'path': 'aegis/management/cloudflare/tunnel/create',
        'body': {'aegisClientId': 'C.legacy'},
    }]
    assert 'endpointAgentId' not in api.calls[0]['body']


def test_remove_cloudflare_tunnel_posts_endpoint_uuid_only():
    api = FakeAPI({'aegis/management/cloudflare/tunnel/remove': {'taskId': 'task-2'}})

    result = Aegis(api).remove_cloudflare_tunnel(' endpoint-1 ')

    assert result == {'taskId': 'task-2'}
    assert api.calls == [{
        'method': 'POST',
        'path': 'aegis/management/cloudflare/tunnel/remove',
        'body': {'endpointAgentId': 'endpoint-1'},
    }]
    assert 'aegisClientId' not in api.calls[0]['body']


def test_remove_cloudflare_tunnel_posts_legacy_client_id():
    api = FakeAPI()

    Aegis(api).remove_cloudflare_tunnel(' C.legacy ', legacy=True)

    assert api.calls == [{
        'method': 'POST',
        'path': 'aegis/management/cloudflare/tunnel/remove',
        'body': {'aegisClientId': 'C.legacy'},
    }]
    assert 'endpointAgentId' not in api.calls[0]['body']


@pytest.mark.parametrize('method', [
    'get_cloudflare_tunnel_status',
    'create_cloudflare_tunnel',
    'remove_cloudflare_tunnel',
])
def test_cloudflare_tunnel_methods_require_endpoint_uuid(method):
    with pytest.raises(ValueError, match='endpoint ID is required'):
        getattr(Aegis(FakeAPI()), method)('  ')
