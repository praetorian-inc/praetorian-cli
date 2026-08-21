"""Unit tests for multipart upload CLI commands (ST-21)."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.multipart  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.multipart.create.return_value = {'uploadId': 'upload-123'}
    sdk.multipart.get_part_url.return_value = {'url': 'https://s3.example.com/part'}
    sdk.multipart.complete.return_value = {'status': 'completed'}
    sdk.multipart.abort.return_value = {'status': 'aborted'}
    return sdk


def _invoke(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


def test_create(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'multipart', 'create', '--name', 'large-file.zip',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.multipart.create.assert_called_once_with('large-file.zip', praetorian=False, ttl=None)


def test_create_with_praetorian(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'multipart', 'create', '--name', 'report.pdf', '--praetorian', '--ttl', '3600',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.multipart.create.assert_called_once_with('report.pdf', praetorian=True, ttl=3600)


def test_part_url(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'multipart', 'part-url',
        '--name', 'large-file.zip',
        '--upload-id', 'upload-123',
        '--part-number', '1',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.multipart.get_part_url.assert_called_once_with(
        'large-file.zip', 'upload-123', 1, praetorian=False,
    )


def test_complete(runner, fake_sdk):
    stdin = '{"name": "large-file.zip", "uploadId": "upload-123", "parts": [{"partNumber": 1, "etag": "abc"}]}'
    result = _invoke(runner, fake_sdk, ['multipart', 'complete'], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.multipart.complete.assert_called_once_with(
        'large-file.zip', 'upload-123', [{'partNumber': 1, 'etag': 'abc'}], praetorian=False,
    )


def test_abort(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'multipart', 'abort',
        '--name', 'large-file.zip',
        '--upload-id', 'upload-123',
        '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.multipart.abort.assert_called_once_with('large-file.zip', 'upload-123', praetorian=False)
