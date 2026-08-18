"""Unit tests for plextrac CLI commands."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.plextrac  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.plextrac.create_finding.return_value = {'status': 'created'}
    sdk.plextrac.get_reports.return_value = [{'id': 1}]
    sdk.plextrac.export.return_value = {'url': 'https://example.com/report.pdf'}
    sdk.plextrac.connect_report.return_value = {'status': 'connected'}
    sdk.plextrac.disconnect_report.return_value = {'status': 'disconnected'}
    sdk.plextrac.update_definition.return_value = {'status': 'updated'}
    return sdk


def _invoke(runner, fake_sdk, argv, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, **kwargs)


def test_create_finding(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'plextrac', 'create-finding', '--risk-key', 'CVE-2024-1234', '--report-id', '100',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.create_finding.assert_called_once_with('CVE-2024-1234', 100)


def test_reports(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['plextrac', 'reports'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.get_reports.assert_called_once_with(published=False)


def test_reports_published(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['plextrac', 'reports', '--published'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.get_reports.assert_called_once_with(published=True)


def test_export(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['plextrac', 'export', '--report-id', '100'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.export.assert_called_once_with(100)


def test_connect(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['plextrac', 'connect', '--report-id', '100'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.connect_report.assert_called_once_with(100)


def test_disconnect(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'plextrac', 'disconnect', '--report-id', '100', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.disconnect_report.assert_called_once_with(100)


def test_update_definition(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'plextrac', 'update-definition', '--risk-key', 'CVE-2024-1234',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.plextrac.update_definition.assert_called_once_with('CVE-2024-1234')
