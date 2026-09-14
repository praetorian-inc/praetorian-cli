"""CLI-level tests for `guard add file` destination-partition resolution.

`--name` and the Praetorian partition used to be mutually exclusive by construction:
`praetorian` was initialised `False` and only reassigned inside the `elif
sdk.is_praetorian_user()` auto-placement branch, which `--name` skips. So
`guard add file f -n reports/narratives.md` silently landed in the tenant's default
partition, where the Generate Report wizard -- which lists only `reports/*.md` in the
Praetorian partition -- could not see it. These tests pin that the path and the
partition are now chosen independently, and that the flag stays gated.

Offline: the SDK is a MagicMock and the update advisory is stubbed out, so nothing
here touches the network.
"""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.add import add


@pytest.fixture
def local_file(tmp_path):
    f = tmp_path / 'narratives.md'
    f.write_text('# Narratives\n')
    return str(f)


def _sdk(is_praetorian_user=True, username='op@praetorian.com'):
    sdk = MagicMock()
    sdk.is_praetorian_user.return_value = is_praetorian_user
    # Real profiles either carry a username or authenticate with an API key, in
    # which case username() is None. MagicMock's default is truthy, so it is set
    # explicitly here -- the difference decides whether the local gate fires.
    sdk.keychain.username.return_value = username
    return sdk


def _invoke(sdk, *args):
    with patch('praetorian_cli.handlers.cli_decorators._check_for_update', lambda: None):
        return CliRunner().invoke(add, ['file', *args], obj=sdk)


def test_named_upload_with_flag_targets_praetorian_partition(local_file):
    sdk = _sdk()
    result = _invoke(sdk, local_file, '--name', 'reports/narratives.md', '--praetorian')

    assert result.exit_code == 0, result.output
    args, kwargs = sdk.files.add.call_args
    assert args[1] == 'reports/narratives.md'
    assert kwargs['praetorian'] is True


def test_named_upload_without_flag_keeps_default_partition(local_file):
    """Back-compat: absent the flag, `--name` behaves exactly as before."""
    sdk = _sdk()
    result = _invoke(sdk, local_file, '--name', 'reports/narratives.md')

    assert result.exit_code == 0, result.output
    args, kwargs = sdk.files.add.call_args
    assert args[1] == 'reports/narratives.md'
    assert kwargs['praetorian'] is False


def test_auto_placement_is_unchanged(local_file):
    """No --name: a Praetorian user still auto-lands in the internal partition."""
    sdk = _sdk()
    result = _invoke(sdk, local_file)

    assert result.exit_code == 0, result.output
    args, kwargs = sdk.files.add.call_args
    assert args[1] == 'home/internal/narratives.md'
    assert kwargs['praetorian'] is True


def test_flag_is_rejected_for_known_non_praetorian_caller(local_file):
    """Mirrors the backend 403 locally instead of failing after the round trip."""
    sdk = _sdk(is_praetorian_user=False, username='customer@example.com')
    result = _invoke(sdk, local_file, '--name', 'reports/narratives.md', '--praetorian')

    assert result.exit_code != 0
    assert 'Praetorian engineers only' in result.output
    sdk.files.add.assert_not_called()


def test_api_key_profile_is_not_blocked_locally(local_file):
    """An API-key profile has no username, so is_praetorian_user() is False even
    for a Praetorian operator. Gating on it alone would make the flag unusable on
    exactly the engagement profiles it exists for -- verified against a live
    tenant, where the backend accepted praetorian=true from such a profile. The
    local gate must defer to the backend when the identity is unknown."""
    sdk = _sdk(is_praetorian_user=False, username=None)
    result = _invoke(sdk, local_file, '--name', 'reports/narratives.md', '--praetorian')

    assert result.exit_code == 0, result.output
    args, kwargs = sdk.files.add.call_args
    assert args[1] == 'reports/narratives.md'
    assert kwargs['praetorian'] is True


def test_flag_conflicts_with_public(local_file):
    sdk = _sdk()
    result = _invoke(sdk, local_file, '--name', 'reports/x.md', '--praetorian', '--public')

    assert result.exit_code != 0
    assert 'mutually exclusive' in result.output
    sdk.files.add.assert_not_called()


def test_help_advertises_the_flag():
    result = CliRunner().invoke(add, ['file', '--help'])

    assert result.exit_code == 0
    assert '--praetorian' in result.output
