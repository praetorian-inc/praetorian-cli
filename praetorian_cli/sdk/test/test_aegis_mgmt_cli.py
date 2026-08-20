from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import praetorian_cli.handlers.aegis  # noqa: F401
from praetorian_cli.handlers.chariot import chariot


def _invoke(*args, stdin=None):
    runner = CliRunner()
    mock_sdk = MagicMock()
    mock_sdk.is_praetorian_user.return_value = True
    mock_sdk.aegis.management_capabilities.return_value = [{'name': 'sysmon'}]
    mock_sdk.aegis.management_tasks.return_value = [{'taskId': 't1'}]
    mock_sdk.aegis.create_management_task.return_value = {'taskId': 't2', 'status': 'AMT_PENDING'}
    mock_sdk.aegis.cancel_management_task.return_value = {'status': 'cancelled'}
    mock_sdk.aegis.create_tunnel.return_value = {'hostname': 'x.zone.domain'}
    mock_sdk.aegis.remove_tunnel.return_value = {'taskId': 't3'}
    mock_sdk.aegis.provision.return_value = {'org_id': 'org-1'}
    mock_sdk.aegis.installer.return_value = {'url': 'https://s3/installer.deb'}
    mock_sdk.aegis.reachability_agent.return_value = {'results': [], 'count': 0}
    mock_sdk.aegis.reachability_asset.return_value = {'results': [], 'count': 0}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
            input=stdin,
        )
    return result, mock_sdk


# --- Installer ---

def test_installer():
    result, sdk = _invoke('aegis', 'installer', '--flavor', 'deb')
    assert result.exit_code == 0
    sdk.aegis.installer.assert_called_once_with('deb', proxy_configuration=None)


def test_installer_with_proxy():
    result, sdk = _invoke('aegis', 'installer', '--flavor', 'msi',
                          '--proxy', 'http://proxy:8080')
    assert result.exit_code == 0
    sdk.aegis.installer.assert_called_once_with('msi', proxy_configuration='http://proxy:8080')


def test_installer_invalid_flavor():
    result, _ = _invoke('aegis', 'installer', '--flavor', 'exe')
    assert result.exit_code != 0


# --- Provision ---

def test_provision():
    result, sdk = _invoke('aegis', 'provision', '--tenant', 'user@praetorian.com')
    assert result.exit_code == 0
    sdk.aegis.provision.assert_called_once_with('user@praetorian.com')


def test_provision_missing_tenant():
    result, _ = _invoke('aegis', 'provision')
    assert result.exit_code != 0


# --- Management capabilities ---

def test_capabilities():
    result, sdk = _invoke('aegis', 'capabilities')
    assert result.exit_code == 0
    sdk.aegis.management_capabilities.assert_called_once_with(
        name=None, target=None, executor=None, runs_on=None, integration=None)


def test_capabilities_with_filters():
    result, sdk = _invoke('aegis', 'capabilities', '--runs-on', 'windows',
                          '--target', 'agent')
    assert result.exit_code == 0
    sdk.aegis.management_capabilities.assert_called_once_with(
        name=None, target='agent', executor=None, runs_on='windows', integration=None)


def test_capabilities_with_integration():
    result, sdk = _invoke('aegis', 'capabilities', '--integration')
    assert result.exit_code == 0
    sdk.aegis.management_capabilities.assert_called_once_with(
        name=None, target=None, executor=None, runs_on=None, integration=True)


def test_capabilities_with_no_integration():
    result, sdk = _invoke('aegis', 'capabilities', '--no-integration')
    assert result.exit_code == 0
    sdk.aegis.management_capabilities.assert_called_once_with(
        name=None, target=None, executor=None, runs_on=None, integration=False)


# --- Management tasks ---

def test_tasks():
    result, sdk = _invoke('aegis', 'tasks')
    assert result.exit_code == 0
    sdk.aegis.management_tasks.assert_called_once_with(key=None)


def test_tasks_by_key():
    result, sdk = _invoke('aegis', 'tasks', '--key', 'task-123')
    assert result.exit_code == 0
    sdk.aegis.management_tasks.assert_called_once_with(key='task-123')


def test_create_task():
    result, sdk = _invoke(
        'aegis', 'create-task',
        '--capability', 'install-sysmon',
        '--client-id', 'C.abc123')
    assert result.exit_code == 0
    sdk.aegis.create_management_task.assert_called_once_with(
        'install-sysmon', 'C.abc123',
        agent_id=None, parameters=None, async_=False, health_check=False)


def test_create_task_with_params():
    result, sdk = _invoke(
        'aegis', 'create-task',
        '--capability', 'run-script',
        '--client-id', 'C.abc123',
        '--parameters', '{"script":"test.ps1"}',
        '--health-check')
    assert result.exit_code == 0
    sdk.aegis.create_management_task.assert_called_once_with(
        'run-script', 'C.abc123',
        agent_id=None, parameters={'script': 'test.ps1'},
        async_=False, health_check=True)


def test_create_task_missing_capability():
    result, _ = _invoke('aegis', 'create-task', '--client-id', 'C.abc123')
    assert result.exit_code != 0


def test_cancel_task():
    result, sdk = _invoke('aegis', 'cancel-task', '--key', 'task-123')
    assert result.exit_code == 0
    sdk.aegis.cancel_management_task.assert_called_once_with('task-123')


# --- Cloudflare tunnels ---

def test_tunnel_create():
    result, sdk = _invoke('aegis', 'tunnel-create', '--client-id', 'C.abc123')
    assert result.exit_code == 0
    sdk.aegis.create_tunnel.assert_called_once_with('C.abc123')


def test_tunnel_remove_with_force():
    result, sdk = _invoke('aegis', 'tunnel-remove', '--client-id', 'C.abc123', '--force')
    assert result.exit_code == 0
    sdk.aegis.remove_tunnel.assert_called_once_with('C.abc123')


def test_tunnel_remove_confirmed():
    result, sdk = _invoke('aegis', 'tunnel-remove', '--client-id', 'C.abc123', stdin='y\n')
    assert result.exit_code == 0
    sdk.aegis.remove_tunnel.assert_called_once_with('C.abc123')


def test_tunnel_remove_aborted():
    result, sdk = _invoke('aegis', 'tunnel-remove', '--client-id', 'C.abc123', stdin='n\n')
    assert result.exit_code != 0
    sdk.aegis.remove_tunnel.assert_not_called()


# --- Reachability ---

def test_reachability_agent():
    result, sdk = _invoke('aegis', 'reachability-agent', '--client-id', 'C.abc123')
    assert result.exit_code == 0
    sdk.aegis.reachability_agent.assert_called_once_with('C.abc123', limit=None, offset=None)


def test_reachability_agent_with_limit():
    result, sdk = _invoke('aegis', 'reachability-agent', '--client-id', 'C.abc123',
                          '--limit', '50')
    assert result.exit_code == 0
    sdk.aegis.reachability_agent.assert_called_once_with('C.abc123', limit=50, offset=None)


def test_reachability_agent_with_limit_and_offset():
    result, sdk = _invoke('aegis', 'reachability-agent', '--client-id', 'C.abc123',
                          '--limit', '50', '--offset', '100')
    assert result.exit_code == 0
    sdk.aegis.reachability_agent.assert_called_once_with('C.abc123', limit=50, offset=100)


def test_reachability_asset():
    result, sdk = _invoke('aegis', 'reachability-asset', '--key', '#asset#10.0.1.5')
    assert result.exit_code == 0
    sdk.aegis.reachability_asset.assert_called_once_with('#asset#10.0.1.5')


def test_reachability_asset_missing_key():
    result, _ = _invoke('aegis', 'reachability-asset')
    assert result.exit_code != 0
