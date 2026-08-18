"""Unit tests for leaderboard CLI commands."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.leaderboard  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = True
    sdk.leaderboard.get.return_value = [{'rank': 1, 'name': 'Engineer A', 'score': 100}]
    sdk.leaderboard.get_weights.return_value = {'critical': 10, 'high': 5, 'medium': 2}
    sdk.leaderboard.set_weights.return_value = {'status': 'updated'}
    return sdk


def _invoke(runner, fake_sdk, argv, input=None, **kwargs):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, input=input, **kwargs)


def test_get_leaderboard(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['leaderboard', 'get'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.leaderboard.get.assert_called_once()


def test_get_weights(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['leaderboard', 'get-weights'], catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.leaderboard.get_weights.assert_called_once()


def test_set_weights(runner, fake_sdk):
    stdin = '{"critical": 15, "high": 8, "medium": 3}'
    result = _invoke(runner, fake_sdk, ['leaderboard', 'set-weights'], input=stdin, catch_exceptions=False)
    assert result.exit_code == 0
    fake_sdk.leaderboard.set_weights.assert_called_once_with({
        'critical': 15, 'high': 8, 'medium': 3,
    })


def test_set_weights_no_stdin(runner, fake_sdk):
    result = _invoke(runner, fake_sdk, ['leaderboard', 'set-weights'], input='', catch_exceptions=True)
    assert result.exit_code != 0 or 'ERROR' in result.output
