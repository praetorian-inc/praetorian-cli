"""Unit tests for hackerone CLI commands."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.hackerone  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.hackerone.sync_scope.return_value = {'status': 'ok'}
    sdk.hackerone.programs.return_value = [{'handle': 'acme'}]
    sdk.hackerone.program_scopes.return_value = [{'scope': 'example.com'}]
    sdk.hackerone.program_weaknesses.return_value = [{'id': 1}]
    sdk.hackerone.comment.return_value = {'id': '123'}
    sdk.hackerone.activities.return_value = [{'type': 'comment'}]
    sdk.hackerone.severity.return_value = {'status': 'updated'}
    sdk.hackerone.bounty_catalog.return_value = [{'program': 'acme'}]
    return sdk


def _invoke(runner, fake_sdk, argv, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, **kwargs)


def test_sync_scope(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'sync-scope'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.sync_scope.assert_called_once()


def test_programs(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'programs'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.programs.assert_called_once()


def test_scopes(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'scopes', 'acme'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.program_scopes.assert_called_once_with('acme')


def test_weaknesses(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'weaknesses', 'acme'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.program_weaknesses.assert_called_once_with('acme')


def test_comment(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'hackerone', 'comment', '42', 'Test message',
        '--internal', '--source', 'org-api',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.comment.assert_called_once_with(
        '42', 'Test message', internal=True, source='org-api',
    )


def test_activities(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'activities', '42'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.activities.assert_called_once_with('42', source='hacker-api')


def test_severity(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'severity', '42', 'critical'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.severity.assert_called_once_with('42', 'critical')


def test_bounty_catalog(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['hackerone', 'bounty-catalog'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.hackerone.bounty_catalog.assert_called_once()
