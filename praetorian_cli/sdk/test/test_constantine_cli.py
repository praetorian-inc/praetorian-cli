from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import praetorian_cli.handlers.constantine  # noqa: F401
import praetorian_cli.handlers.osint  # noqa: F401
import praetorian_cli.handlers.remediation  # noqa: F401
from praetorian_cli.handlers.chariot import chariot


def _invoke(*args):
    runner = CliRunner()
    mock_sdk = MagicMock()
    mock_sdk.constantine.exploit.return_value = {'status': 'ok'}
    mock_sdk.constantine.patch.return_value = {'status': 'ok'}
    mock_sdk.constantine.patch_and_pr.return_value = {'status': 'ok'}
    mock_sdk.constantine.validate.return_value = {'status': 'ok'}
    mock_sdk.constantine.manifest.return_value = {'presets': []}
    mock_sdk.osint.guess_repo.return_value = {'repo': 'https://github.com/org/repo'}
    mock_sdk.osint.submit.return_value = {'status': 'ok'}
    mock_sdk.osint.create_technology.return_value = {'status': 'ok'}
    mock_sdk.remediation.select_patch.return_value = {'status': 'ok'}
    mock_sdk.remediation.clear_patch.return_value = {'status': 'ok'}
    mock_sdk.remediation.create_pr.return_value = {'status': 'ok'}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
        )
    return result, mock_sdk


# --- Constantine commands ---

def test_constantine_exploit():
    result, sdk = _invoke('constantine', 'exploit', '--risk-keys', 'key1,key2')
    assert result.exit_code == 0
    sdk.constantine.exploit.assert_called_once_with(['key1', 'key2'])


def test_constantine_exploit_single_key():
    result, sdk = _invoke('constantine', 'exploit', '--risk-keys', '#risk#example.com#CVE-1')
    assert result.exit_code == 0
    sdk.constantine.exploit.assert_called_once_with(['#risk#example.com#CVE-1'])


def test_constantine_exploit_missing_keys():
    result, _ = _invoke('constantine', 'exploit')
    assert result.exit_code != 0


def test_constantine_patch():
    result, sdk = _invoke('constantine', 'patch', '--risk-keys', 'key1,key2')
    assert result.exit_code == 0
    sdk.constantine.patch.assert_called_once_with(['key1', 'key2'])


def test_constantine_patch_missing_keys():
    result, _ = _invoke('constantine', 'patch')
    assert result.exit_code != 0


def test_constantine_patch_and_pr():
    result, sdk = _invoke('constantine', 'patch-and-pr', '--risk-key', '#risk#ex#CVE-1')
    assert result.exit_code == 0
    sdk.constantine.patch_and_pr.assert_called_once_with('#risk#ex#CVE-1')


def test_constantine_patch_and_pr_missing_key():
    result, _ = _invoke('constantine', 'patch-and-pr')
    assert result.exit_code != 0


def test_constantine_validate():
    result, sdk = _invoke('constantine', 'validate', '--risk-keys', 'k1,k2,k3')
    assert result.exit_code == 0
    sdk.constantine.validate.assert_called_once_with(['k1', 'k2', 'k3'])


def test_constantine_manifest():
    result, sdk = _invoke('constantine', 'manifest')
    assert result.exit_code == 0
    sdk.constantine.manifest.assert_called_once()


# --- OSINT commands ---

def test_osint_guess_repo_with_cpe():
    result, sdk = _invoke('osint', 'guess-repo', '--cpe', 'cpe:2.3:a:apache:httpd')
    assert result.exit_code == 0
    sdk.osint.guess_repo.assert_called_once_with(cpe='cpe:2.3:a:apache:httpd', technology_name=None)


def test_osint_guess_repo_with_name():
    result, sdk = _invoke('osint', 'guess-repo', '--technology-name', 'OpenSSL')
    assert result.exit_code == 0
    sdk.osint.guess_repo.assert_called_once_with(cpe=None, technology_name='OpenSSL')


def test_osint_guess_repo_no_args():
    result, _ = _invoke('osint', 'guess-repo')
    assert 'ERROR' in result.output


def test_osint_submit():
    result, sdk = _invoke('osint', 'submit', '--repo-url', 'https://github.com/org/repo')
    assert result.exit_code == 0
    sdk.osint.submit.assert_called_once_with(
        'https://github.com/org/repo',
        technology_key=None, goal=None, pipeline=None, scan_mode=None)


def test_osint_submit_with_options():
    result, sdk = _invoke(
        'osint', 'submit',
        '--repo-url', 'https://github.com/org/repo',
        '--pipeline', 'premium-legacy',
        '--scan-mode', 'full')
    assert result.exit_code == 0
    sdk.osint.submit.assert_called_once_with(
        'https://github.com/org/repo',
        technology_key=None, goal=None, pipeline='premium-legacy', scan_mode='full')


def test_osint_submit_missing_url():
    result, _ = _invoke('osint', 'submit')
    assert result.exit_code != 0


def test_osint_submit_invalid_scan_mode():
    result, _ = _invoke('osint', 'submit', '--repo-url', 'https://x.com/r', '--scan-mode', 'bad')
    assert result.exit_code != 0


def test_osint_create_technology():
    result, sdk = _invoke('osint', 'create-technology', '--cpe', 'cpe:2.3:a:openssl:openssl:3.0.0')
    assert result.exit_code == 0
    sdk.osint.create_technology.assert_called_once_with('cpe:2.3:a:openssl:openssl:3.0.0')


def test_osint_create_technology_missing_cpe():
    result, _ = _invoke('osint', 'create-technology')
    assert result.exit_code != 0


# --- Remediation commands ---

def test_remediation_select():
    result, sdk = _invoke(
        'remediation', 'select',
        '--risk-key', 'rk1', '--finding-id', 'f1', '--option-id', 'opt1')
    assert result.exit_code == 0
    sdk.remediation.select_patch.assert_called_once_with('rk1', 'f1', 'opt1', strategy=None)


def test_remediation_select_with_strategy():
    result, sdk = _invoke(
        'remediation', 'select',
        '--risk-key', 'rk1', '--finding-id', 'f1', '--option-id', 'opt1',
        '--strategy', 'minimal')
    assert result.exit_code == 0
    sdk.remediation.select_patch.assert_called_once_with('rk1', 'f1', 'opt1', strategy='minimal')


def test_remediation_select_missing_required():
    result, _ = _invoke('remediation', 'select', '--risk-key', 'rk1')
    assert result.exit_code != 0


def test_remediation_clear():
    result, sdk = _invoke(
        'remediation', 'clear', '--risk-key', 'rk1', '--finding-id', 'f1')
    assert result.exit_code == 0
    sdk.remediation.clear_patch.assert_called_once_with('rk1', 'f1')


def test_remediation_clear_missing_required():
    result, _ = _invoke('remediation', 'clear', '--risk-key', 'rk1')
    assert result.exit_code != 0


def test_remediation_create_pr():
    result, sdk = _invoke(
        'remediation', 'create-pr', '--risk-key', 'rk1', '--finding-id', 'f1')
    assert result.exit_code == 0
    sdk.remediation.create_pr.assert_called_once_with('rk1', 'f1')


def test_remediation_create_pr_missing_required():
    result, _ = _invoke('remediation', 'create-pr', '--risk-key', 'rk1')
    assert result.exit_code != 0
