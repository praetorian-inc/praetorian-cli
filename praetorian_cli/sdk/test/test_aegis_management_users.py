import pytest

from praetorian_cli.sdk.entities.aegis import Aegis


class FakeAPI:
    def __init__(self):
        self.calls = []

    def post(self, path, body):
        self.calls.append({'path': path, 'body': body})
        return {'taskId': 'task-1', 'status': 'AMT_RUNNING'}


def test_add_system_user_posts_endpoint_management_task_without_legacy_client_id():
    api = FakeAPI()

    result = Aegis(api).add_system_user(' endpoint-1 ', ' pentester ')

    assert result == {'taskId': 'task-1', 'status': 'AMT_RUNNING'}
    assert api.calls == [{
        'path': 'aegis/management/tasks',
        'body': {
            'aegisManagementCapability': 'linux-system-adduser',
            'parameters': {
                'endpoint_agent_id': 'endpoint-1',
                'username': 'pentester',
            },
        },
    }]
    assert 'aegisClientId' not in api.calls[0]['body']


def test_remove_system_user_posts_endpoint_management_task_without_legacy_client_id():
    api = FakeAPI()

    Aegis(api).remove_system_user(' endpoint-1 ', ' pentester ', remove_home=True)

    assert api.calls == [{
        'path': 'aegis/management/tasks',
        'body': {
            'aegisManagementCapability': 'linux-system-deluser',
            'parameters': {
                'endpoint_agent_id': 'endpoint-1',
                'username': 'pentester',
                'remove_home': '--remove-home',
            },
        },
    }]
    assert 'aegisClientId' not in api.calls[0]['body']


@pytest.mark.parametrize('method', ['add_system_user', 'remove_system_user'])
def test_system_user_methods_require_endpoint_uuid(method):
    with pytest.raises(ValueError, match='endpoint ID is required'):
        getattr(Aegis(FakeAPI()), method)('  ', 'pentester')


@pytest.mark.parametrize('method', ['add_system_user', 'remove_system_user'])
def test_system_user_methods_require_username(method):
    with pytest.raises(ValueError, match='username is required'):
        getattr(Aegis(FakeAPI()), method)('endpoint-1', '  ')
