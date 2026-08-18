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


# --- Tests for new export commands (entity, loa, health) ---

def _invoke_with_input(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


@pytest.fixture
def export_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.exports.export_entity.return_value = {'job_id': 'abc'}
    sdk.exports.export_loa.return_value = {'url': 'https://example.com/loa.pdf'}
    sdk.exports.health_report.return_value = {'status': 'healthy'}
    return sdk


def test_export_entity(runner, export_sdk):
    stdin = '{"items": ["#asset#1", "#asset#2"]}'
    result = _invoke_with_input(runner, export_sdk, [
        'export', 'entity', 'assets', '--format', 'json',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    export_sdk.exports.export_entity.assert_called_once_with(
        'assets', items=['#asset#1', '#asset#2'], query=None, format='json', columns=None,
    )


def test_export_entity_with_columns(runner, export_sdk):
    stdin = '{"query": {"status": "A"}}'
    result = _invoke_with_input(runner, export_sdk, [
        'export', 'entity', 'risks', '--columns', 'name,severity,status',
    ], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    export_sdk.exports.export_entity.assert_called_once_with(
        'risks', items=None, query={'status': 'A'}, format='csv',
        columns=['name', 'severity', 'status'],
    )


def test_export_entity_no_stdin(runner, export_sdk):
    result = _invoke_with_input(runner, export_sdk, [
        'export', 'entity', 'assets',
    ], input='', catch_exceptions=True)
    assert result.exit_code != 0 or 'ERROR' in result.output


def test_export_loa(runner, export_sdk):
    stdin = '{"config": {"client_name": "Acme", "content": "test"}}'
    result = _invoke_with_input(runner, export_sdk, ['export', 'loa'], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    export_sdk.exports.export_loa.assert_called_once_with({
        'config': {'client_name': 'Acme', 'content': 'test'},
    })


def test_export_loa_no_stdin(runner, export_sdk):
    result = _invoke_with_input(runner, export_sdk, ['export', 'loa'], input='', catch_exceptions=True)
    assert result.exit_code != 0 or 'ERROR' in result.output


def test_health(runner, export_sdk):
    result = _invoke_with_input(runner, export_sdk, ['export', 'health'], catch_exceptions=False)
    assert result.exit_code == 0
    export_sdk.exports.health_report.assert_called_once()
