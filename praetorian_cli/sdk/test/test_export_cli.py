"""CLI-level tests for `guard export report` flag forwarding."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.export  # noqa: F401 — register export group on chariot
from praetorian_cli.handlers.chariot import chariot


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.reports.customer_email.return_value = 'customer@acme.com'
    sdk.reports.build_export_body.return_value = {'config': {}}
    sdk.reports.export.return_value = {'config': {'output': 'home/report.pdf'}}
    sdk.reports.output_path.return_value = 'home/report.pdf'
    return sdk


def _invoke(runner, fake_sdk, argv):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, catch_exceptions=False)


def test_sow_flag_forwarded_to_build_export_body(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'export', 'report',
        '--title', 'Test Report',
        '--client-name', 'Acme',
        '--sow', 'SOW-2026-TEST',
        '--no-download',
    ])
    assert result.exit_code == 0
    kwargs = fake_sdk.reports.build_export_body.call_args.kwargs
    assert kwargs['sow'] == 'SOW-2026-TEST'


def test_footer_flag_forwarded_to_build_export_body(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'export', 'report',
        '--title', 'Test Report',
        '--client-name', 'Acme',
        '--footer', 'Acme | Q2 External Assessment',
        '--no-download',
    ])
    assert result.exit_code == 0
    kwargs = fake_sdk.reports.build_export_body.call_args.kwargs
    assert kwargs['footer'] == 'Acme | Q2 External Assessment'


def test_confidential_label_flag_forwarded_to_build_export_body(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'export', 'report',
        '--title', 'Test Report',
        '--client-name', 'Acme',
        '--confidential-label', 'Privileged & Confidential',
        '--no-download',
    ])
    assert result.exit_code == 0
    kwargs = fake_sdk.reports.build_export_body.call_args.kwargs
    assert kwargs['confidential_label'] == 'Privileged & Confidential'


def test_all_three_flags_together(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'export', 'report',
        '--title', 'Test Report',
        '--client-name', 'Acme',
        '--sow', 'SOW-2026-TEST',
        '--footer', 'Acme | Q2',
        '--confidential-label', 'Internal Use Only',
        '--no-download',
    ])
    assert result.exit_code == 0
    kwargs = fake_sdk.reports.build_export_body.call_args.kwargs
    assert kwargs['sow'] == 'SOW-2026-TEST'
    assert kwargs['footer'] == 'Acme | Q2'
    assert kwargs['confidential_label'] == 'Internal Use Only'


def test_new_flags_default_to_empty_when_omitted(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'export', 'report',
        '--title', 'Test Report',
        '--client-name', 'Acme',
        '--no-download',
    ])
    assert result.exit_code == 0
    kwargs = fake_sdk.reports.build_export_body.call_args.kwargs
    assert kwargs['sow'] == ''
    assert kwargs['footer'] == ''
    assert kwargs['confidential_label'] == ''
