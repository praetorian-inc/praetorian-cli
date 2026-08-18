from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import praetorian_cli.handlers.knossos  # noqa: F401
from praetorian_cli.handlers.chariot import chariot


def _invoke(*args, stdin=None):
    runner = CliRunner()
    mock_sdk = MagicMock()
    mock_sdk.knossos.profile.return_value = {'style': 'aws'}
    mock_sdk.knossos.profile_infer.return_value = {'inferred': True}
    mock_sdk.knossos.profile_versions.return_value = [{'version': 1}]
    mock_sdk.knossos.generate.return_value = {'id': 'env-1'}
    mock_sdk.knossos.environments.return_value = [{'id': 'env-1'}]
    mock_sdk.knossos.environment.return_value = {'id': 'env-1', 'resources': []}
    mock_sdk.knossos.delete_environment.return_value = {'status': 'deleted'}
    mock_sdk.knossos.emit.return_value = {'hcl': 'resource {}'}
    mock_sdk.knossos.cost.return_value = {'monthly': 42.0}
    mock_sdk.knossos.validate.return_value = {'score': 0.95}
    mock_sdk.knossos.deploy.return_value = {'downloadUrl': 'https://s3/main.tf'}
    mock_sdk.knossos.status.return_value = {'state': 'exported'}
    mock_sdk.knossos.events.return_value = {'data': []}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
            input=stdin,
        )
    return result, mock_sdk


# --- Profile commands ---

def test_profile_get():
    result, sdk = _invoke('knossos', 'profile', 'get')
    assert result.exit_code == 0
    sdk.knossos.profile.assert_called_once()


def test_profile_infer_defaults():
    result, sdk = _invoke('knossos', 'profile', 'infer')
    assert result.exit_code == 0
    sdk.knossos.profile_infer.assert_called_once_with({'provider': 'aws'})


def test_profile_infer_with_options():
    result, sdk = _invoke(
        'knossos', 'profile', 'infer',
        '--provider', 'aws',
        '--regions', 'us-east-1,us-west-2',
        '--lookback-days', '60')
    assert result.exit_code == 0
    sdk.knossos.profile_infer.assert_called_once_with({
        'provider': 'aws',
        'regions': ['us-east-1', 'us-west-2'],
        'lookbackDays': 60,
    })


def test_profile_versions():
    result, sdk = _invoke('knossos', 'profile', 'versions')
    assert result.exit_code == 0
    sdk.knossos.profile_versions.assert_called_once()


# --- Environment commands ---

def test_env_generate():
    body = '{"provider":"aws","attackPaths":[{"goal":"data_exfiltration","routes":1,"depth":[2,5]}]}'
    result, sdk = _invoke('knossos', 'env', 'generate', stdin=body)
    assert result.exit_code == 0
    sdk.knossos.generate.assert_called_once()
    call_body = sdk.knossos.generate.call_args[0][0]
    assert call_body['provider'] == 'aws'
    assert call_body['attackPaths'][0]['goal'] == 'data_exfiltration'


def test_env_list():
    result, sdk = _invoke('knossos', 'env', 'list')
    assert result.exit_code == 0
    sdk.knossos.environments.assert_called_once()


def test_env_get():
    result, sdk = _invoke('knossos', 'env', 'get', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.environment.assert_called_once_with('env-1')


def test_env_get_missing_id():
    result, _ = _invoke('knossos', 'env', 'get')
    assert result.exit_code != 0


def test_env_delete_with_force():
    result, sdk = _invoke('knossos', 'env', 'delete', '--id', 'env-1', '--force')
    assert result.exit_code == 0
    sdk.knossos.delete_environment.assert_called_once_with('env-1')


def test_env_delete_confirmed():
    result, sdk = _invoke('knossos', 'env', 'delete', '--id', 'env-1', stdin='y\n')
    assert result.exit_code == 0
    sdk.knossos.delete_environment.assert_called_once_with('env-1')


def test_env_delete_aborted():
    result, sdk = _invoke('knossos', 'env', 'delete', '--id', 'env-1', stdin='n\n')
    assert result.exit_code != 0
    sdk.knossos.delete_environment.assert_not_called()


def test_env_emit():
    result, sdk = _invoke('knossos', 'env', 'emit', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.emit.assert_called_once_with('env-1')


def test_env_cost():
    result, sdk = _invoke('knossos', 'env', 'cost', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.cost.assert_called_once_with('env-1', refresh=False)


def test_env_cost_refresh():
    result, sdk = _invoke('knossos', 'env', 'cost', '--id', 'env-1', '--refresh')
    assert result.exit_code == 0
    sdk.knossos.cost.assert_called_once_with('env-1', refresh=True)


def test_env_validate():
    result, sdk = _invoke('knossos', 'env', 'validate', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.validate.assert_called_once_with('env-1')


def test_env_deploy():
    result, sdk = _invoke('knossos', 'env', 'deploy', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.deploy.assert_called_once_with('env-1')


def test_env_status():
    result, sdk = _invoke('knossos', 'env', 'status', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.status.assert_called_once_with('env-1')


def test_env_events():
    result, sdk = _invoke('knossos', 'env', 'events', '--id', 'env-1')
    assert result.exit_code == 0
    sdk.knossos.events.assert_called_once_with(
        'env-1', since=None, until=None, lure_id=None,
        event_type=None, limit=None)


def test_env_events_with_filters():
    result, sdk = _invoke(
        'knossos', 'env', 'events', '--id', 'env-1',
        '--event-type', 'api_call', '--limit', '50')
    assert result.exit_code == 0
    sdk.knossos.events.assert_called_once_with(
        'env-1', since=None, until=None, lure_id=None,
        event_type='api_call', limit=50)
