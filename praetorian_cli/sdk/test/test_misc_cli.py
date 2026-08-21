"""Unit tests for misc CLI commands (ST-20)."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.misc  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.misc.update_technology.return_value = [{'key': '#technology#cpe:2.3:a:apache:http_server'}]
    sdk.misc.create_ticket.return_value = {'status': 'created'}
    sdk.misc.update_ticket.return_value = {'status': 'refreshed'}
    sdk.misc.delete_ticket.return_value = {'status': 'deleted'}
    sdk.misc.create_monitor.return_value = {'id': 'session-1'}
    sdk.misc.update_monitor.return_value = {'id': 'session-1'}
    sdk.misc.delete_monitor.return_value = {'status': 'cancelled'}
    sdk.misc.set_flag.return_value = {'name': 'enable_knossos'}
    sdk.misc.delete_flag.return_value = {'name': 'enable_knossos'}
    sdk.misc.create_repository.return_value = {'name': 'my-repo'}
    sdk.misc.parse_burp.return_value = {'endpoints': []}
    sdk.misc.notify_vulnerability.return_value = {'status': 'dispatched'}
    sdk.misc.validate_integration.return_value = {'valid': True}
    sdk.misc.jira_transitions.return_value = {'statuses': []}
    sdk.misc.jira_custom_fields.return_value = {'fields': []}
    sdk.misc.jira_priorities.return_value = {'priorities': []}
    sdk.misc.linear_teams.return_value = {'teams': []}
    sdk.misc.linear_workflow_states.return_value = {'states': []}
    sdk.misc.linear_projects.return_value = {'projects': []}
    sdk.misc.risk_visited.return_value = {'status': 'ok'}
    sdk.misc.agent_list.return_value = [{'name': 'agent1'}]
    sdk.misc.agents.return_value = [{'name': 'planner'}]
    sdk.misc.planner_compact.return_value = {'status': 'compacted'}
    sdk.misc.planner_stop.return_value = {'status': 'stopped'}
    sdk.misc.planner_interaction.return_value = {'status': 'ok'}
    sdk.misc.planner_cost.return_value = {'cost': 0.5}
    sdk.misc.delete_planner.return_value = {'status': 'deleted'}
    sdk.misc.put_hunt_memory.return_value = {'status': 'ok'}
    sdk.misc.delete_hunt_memory.return_value = {'status': 'deleted'}
    sdk.misc.hunt_cost.return_value = {'cost': 1.0}
    return sdk


def _invoke(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


def test_update_technology(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'update-technology', '--key', '#technology#cpe:2.3:a:apache', '--name', 'Apache',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.update_technology.assert_called_once()


def test_create_ticket(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'ticket', 'create', '--risk', '#risk#123', '--account', '#account#jira',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.create_ticket.assert_called_once()


def test_delete_ticket(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'ticket', 'delete', '--provider', 'jira', '--ticket-id', 'PROJ-123', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.delete_ticket.assert_called_once()


def test_create_monitor(runner, fake_sdk):
    stdin = '{"name": "test", "techniques": [{"technique_id": "T1", "name": "test"}]}'
    result = _invoke(runner, fake_sdk, ['monitor', 'create'], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.create_monitor.assert_called_once()


def test_delete_monitor(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'monitor', 'delete', '--id', 'session-1', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.delete_monitor.assert_called_once_with('session-1')


def test_set_flag(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['flag', 'set', 'enable_knossos'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.set_flag.assert_called_once_with('enable_knossos')


def test_delete_flag(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'flag', 'delete', 'enable_knossos', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.delete_flag.assert_called_once_with('enable_knossos')


def test_add_repository(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'add-repository', '--name', 'my-repo', '--source-archive-key', 's3key',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.create_repository.assert_called_once_with('my-repo', 's3key')


def test_parse_burp_url(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'parse-burp', '--url', 'https://example.com/api.yaml',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.parse_burp.assert_called_once_with(url='https://example.com/api.yaml')


def test_validate_integration(runner, fake_sdk):
    stdin = '{"provider": "jira", "secret": {"token": "abc"}}'
    result = _invoke(runner, fake_sdk, [
        'integration-setup', 'validate',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.validate_integration.assert_called_once()


def test_risk_visited(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'risk-visited', '#risk#123', '--comment', 'reviewed',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.risk_visited.assert_called_once_with('#risk#123', 'reviewed')


def test_agent_list(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['agent-list'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.agent_list.assert_called_once()


def test_agents(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['agents'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.agents.assert_called_once()


def test_planner_cost(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'planner', 'cost', '550e8400-e29b-41d4-a716-446655440000',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.planner_cost.assert_called_once_with('550e8400-e29b-41d4-a716-446655440000')


def test_delete_planner(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'planner', 'delete', '550e8400-e29b-41d4-a716-446655440000', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.delete_planner.assert_called_once()


def test_set_hunt_memory(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'set-hunt-memory', 'uuid1', 'findings',
    ], input='Important findings here', catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.put_hunt_memory.assert_called_once_with('uuid1', 'findings', 'Important findings here')


def test_hunt_cost(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hunt-cost', 'uuid1'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.misc.hunt_cost.assert_called_once_with('uuid1')
