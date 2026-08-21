from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import praetorian_cli.handlers.enrichment_admin  # noqa: F401
from praetorian_cli.handlers.chariot import chariot


def _invoke(*args, stdin=None):
    runner = CliRunner()
    mock_sdk = MagicMock()
    mock_sdk.enrichment_admin.status.return_value = {'enabled': True}
    mock_sdk.enrichment_admin.enabled.return_value = {'plugins': []}
    mock_sdk.enrichment_admin.global_enabled.return_value = {'enabled': True}
    mock_sdk.enrichment_admin.set_global_enabled.return_value = {'status': 'ok'}
    mock_sdk.enrichment_admin.credits.return_value = {'credits': 100}
    mock_sdk.enrichment_admin.plugin_status.return_value = {'status': 'active'}
    mock_sdk.enrichment_admin.plugin_credits.return_value = {'credits': 50}
    mock_sdk.enrichment_admin.set_plugin_enabled.return_value = {'status': 'ok'}
    mock_sdk.enrichment_admin.set_plugin_key.return_value = {'status': 'ok'}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
            input=stdin,
        )
    return result, mock_sdk


def test_enrichment_status():
    result, sdk = _invoke('enrichment', 'status')
    assert result.exit_code == 0
    sdk.enrichment_admin.status.assert_called_once()


def test_enrichment_enabled():
    result, sdk = _invoke('enrichment', 'enabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.enabled.assert_called_once()


def test_enrichment_global_enabled():
    result, sdk = _invoke('enrichment', 'global-enabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.global_enabled.assert_called_once()


def test_set_global_enabled_on():
    result, sdk = _invoke('enrichment', 'set-global-enabled', '--enabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.set_global_enabled.assert_called_once_with(True)


def test_set_global_enabled_off():
    result, sdk = _invoke('enrichment', 'set-global-enabled', '--disabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.set_global_enabled.assert_called_once_with(False)


def test_enrichment_credits():
    result, sdk = _invoke('enrichment', 'credits')
    assert result.exit_code == 0
    sdk.enrichment_admin.credits.assert_called_once()


def test_plugin_status():
    result, sdk = _invoke('enrichment', 'plugin-status', 'shodan')
    assert result.exit_code == 0
    sdk.enrichment_admin.plugin_status.assert_called_once_with('shodan')


def test_plugin_credits():
    result, sdk = _invoke('enrichment', 'plugin-credits', 'shodan')
    assert result.exit_code == 0
    sdk.enrichment_admin.plugin_credits.assert_called_once_with('shodan')


def test_set_enabled_on():
    result, sdk = _invoke('enrichment', 'set-enabled', 'shodan', '--enabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.set_plugin_enabled.assert_called_once_with('shodan', True)


def test_set_enabled_off():
    result, sdk = _invoke('enrichment', 'set-enabled', 'shodan', '--disabled')
    assert result.exit_code == 0
    sdk.enrichment_admin.set_plugin_enabled.assert_called_once_with('shodan', False)


def test_set_key_from_stdin():
    result, sdk = _invoke('enrichment', 'set-key', 'shodan', stdin='sk-test-key-123\n')
    assert result.exit_code == 0
    sdk.enrichment_admin.set_plugin_key.assert_called_once_with('shodan', 'sk-test-key-123')


def test_set_key_empty_stdin():
    result, _ = _invoke('enrichment', 'set-key', 'shodan', stdin='\n')
    assert 'ERROR' in result.output


def test_plugin_status_missing_plugin():
    result, _ = _invoke('enrichment', 'plugin-status')
    assert result.exit_code != 0
