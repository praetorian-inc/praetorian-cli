"""Unit tests for share CLI commands."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.share  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.share.create.return_value = {'id': 'share-1', 'token': 'abc123'}
    sdk.share.list.return_value = [{'id': 'share-1', 'name': 'test'}]
    sdk.share.delete.return_value = {'status': 'deleted'}
    sdk.share.resolve.return_value = {'id': 'share-1', 'data': {}}
    return sdk


def _invoke(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


def test_create(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'share', 'create', '--name', 'My Share',
    ], input='', catch_exceptions=False)
    assert result.exit_code == 0
    call_args = fake_sdk.share.create.call_args[0][0]
    assert call_args['name'] == 'My Share'


def test_create_with_filter(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'share', 'create', '--name', 'Filtered',
        '--filter', '{"status": "O"}',
    ], input='', catch_exceptions=False)
    assert result.exit_code == 0
    call_args = fake_sdk.share.create.call_args[0][0]
    assert call_args['filter'] == {'status': 'O'}


def test_list(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['share', 'list'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.share.list.assert_called_once()


def test_delete(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, [
        'share', 'delete', 'share-1', '--yes',
    ], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.share.delete.assert_called_once_with('share-1')


def test_resolve(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['share', 'resolve', 'abc123'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.share.resolve.assert_called_once_with('abc123')
