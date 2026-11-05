import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.access import (
    access,
    azure_credential_tenant,
    azure_sp_filename,
    select_azure_credential,
    write_azure_sp_file,
)


ACCOUNT = 'chariot+client@praetorian.com'
CRED_ID = 'caa85634-383f-4293-a995-b1427014408e'
TENANT_A = '11111111-1111-1111-1111-111111111111'
TENANT_B = '22222222-2222-2222-2222-222222222222'
CLIENT_ID = '33333333-3333-3333-3333-333333333333'
ASSERTION = 'federated-token-assertion'


class FakeKeychain:
    def __init__(self, account=ACCOUNT):
        self.account = account
        self.assumed = []

    def assume_role(self, account):
        self.assumed.append(account)
        self.account = account


class FakeCredentials:
    def __init__(self, items=None, *, response=None, raise_exc=None):
        self._items = items or []
        self._response = response
        self._raise = raise_exc
        self.list_calls = []
        self.get_calls = []

    def list(self, *args, **kwargs):
        self.list_calls.append({'args': args, 'kwargs': kwargs})
        return list(self._items), None

    def get(self, credential_id, category, type, format, **kwargs):
        self.get_calls.append({
            'credential_id': credential_id,
            'category': category,
            'type': type,
            'format': format,
            **kwargs,
        })
        if self._raise:
            raise self._raise
        return self._response


class FakeSdk:
    def __init__(self, credentials, account=ACCOUNT):
        self.keychain = FakeKeychain(account)
        self.credentials = credentials


def _azure_cred(credential_id=CRED_ID, tenant=TENANT_A, category='env-integration',
                extra=None):
    cred = {
        'credentialId': credential_id,
        'type': 'azure',
        'category': category,
        'tenantId': tenant,
        'accountKey': f'#account#{ACCOUNT}#azure#{tenant}',
    }
    if extra:
        cred.update(extra)
    return cred


def _token_response(client_id=CLIENT_ID, tenant=TENANT_A, assertion=ASSERTION):
    return {
        'credentialValue': {
            'clientId': client_id,
            'tenantId': tenant,
            'assertion': assertion,
        }
    }


def _sdk(items, **cred_kwargs):
    return FakeSdk(FakeCredentials(items, **cred_kwargs))


def _invoke(sdk, *args):
    return CliRunner().invoke(access, ['azure', *args], obj=sdk)


def _patch_azure_fs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        'praetorian_cli.handlers.access.Path.home',
        lambda *args, **kwargs: tmp_path,
    )
    login_calls = []
    monkeypatch.setattr(
        'praetorian_cli.handlers.access.run_az_login',
        lambda client_id, tenant, assertion: login_calls.append(
            (client_id, tenant, assertion)
        ),
    )
    return login_calls


class TestAccessCLIWiring:

    def test_azure_subcommand_registered(self):
        assert 'azure' in access.commands

    def test_azure_help_lists_flags(self):
        result = CliRunner().invoke(access, ['azure', '--help'])
        assert result.exit_code == 0
        assert '--account' in result.output
        assert '--tenant' in result.output
        assert '--credential' in result.output


class TestAzureSpFilename:

    def test_filename_shape(self):
        name = azure_sp_filename(
            'client', CRED_ID, datetime(2026, 9, 16, 15, 30, 45, tzinfo=timezone.utc)
        )
        assert name == f'client-{CRED_ID}-20260916T153045Z.json'

    @pytest.mark.parametrize('client, credential_id', [
        ('../evil', CRED_ID),
        ('client', '../cred'),
        ('foo/bar', CRED_ID),
        ('client', 'id/nested'),
        (r'foo\bar', CRED_ID),
        ('client', r'id\nested'),
        ('foo..bar', CRED_ID),
        ('client', 'id..x'),
    ])
    def test_rejects_path_separators_and_dotdot(self, client, credential_id):
        with pytest.raises(ValueError):
            azure_sp_filename(client, credential_id)

    def test_dest_stays_under_azure_dir(self, tmp_path):
        name = azure_sp_filename('client', CRED_ID, '20260916T153045Z')
        dest = (tmp_path / '.azure' / name).resolve()
        assert dest.parent == (tmp_path / '.azure').resolve()


class TestWriteAzureSpFile:

    def test_content_and_mode(self, tmp_path):
        dest = tmp_path / 'sp.json'
        write_azure_sp_file(dest, CLIENT_ID, TENANT_A, ASSERTION)

        data = json.loads(dest.read_text())
        assert data == [{
            'client_id': CLIENT_ID,
            'tenant': TENANT_A,
            'client_assertion': ASSERTION,
        }]
        assert oct(dest.stat().st_mode & 0o777) == '0o600'

    def test_mode_is_600_even_if_chmod_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(os, 'chmod', lambda *a, **k: None)
        dest = tmp_path / 'sp.json'
        write_azure_sp_file(dest, CLIENT_ID, TENANT_A, ASSERTION)
        assert oct(dest.stat().st_mode & 0o777) == '0o600'

    def test_creates_missing_parent_0700(self, tmp_path):
        parent = tmp_path / 'azure'
        write_azure_sp_file(parent / 'sp.json', CLIENT_ID, TENANT_A, ASSERTION)
        assert oct(parent.stat().st_mode & 0o777) == '0o700'

    def test_does_not_chmod_existing_parent(self, tmp_path):
        parent = tmp_path / 'azure'
        parent.mkdir()
        parent.chmod(0o755)
        before = parent.stat().st_mode & 0o777
        write_azure_sp_file(parent / 'sp.json', CLIENT_ID, TENANT_A, ASSERTION)
        assert parent.stat().st_mode & 0o777 == before

    def test_existing_file_raises(self, tmp_path):
        dest = tmp_path / 'sp.json'
        write_azure_sp_file(dest, CLIENT_ID, TENANT_A, ASSERTION)
        with pytest.raises(FileExistsError):
            write_azure_sp_file(dest, CLIENT_ID, TENANT_A, ASSERTION)


class TestAzureCredentialTenant:

    def test_tenantId(self):
        assert azure_credential_tenant({'tenantId': TENANT_A}) == TENANT_A

    def test_tenant(self):
        assert azure_credential_tenant({'tenant': TENANT_A}) == TENANT_A

    def test_tenant_id(self):
        assert azure_credential_tenant({'tenant_id': TENANT_A}) == TENANT_A

    def test_account_key_fallback(self):
        cred = {
            'accountKey': f'#account#{ACCOUNT}#azure#{TENANT_B}',
        }
        assert azure_credential_tenant(cred) == TENANT_B


class TestSelectAzureCredential:

    def test_one_cred(self):
        cred = _azure_cred()
        assert select_azure_credential([cred]) is cred

    def test_multi_without_flags_errors(self):
        creds = [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_B)]
        with pytest.raises(SystemExit) as exc:
            select_azure_credential(creds)
        assert exc.value.code == 1

    def test_multi_without_flags_lists_uuid_and_tenant(self, capsys):
        creds = [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_B)]
        with pytest.raises(SystemExit):
            select_azure_credential(creds)
        err = capsys.readouterr().err
        assert CRED_ID in err
        assert TENANT_A in err
        assert 'other-id' in err
        assert TENANT_B in err
        assert '--tenant' in err
        assert '--credential' in err

    def test_tenant_selects_one(self):
        a = _azure_cred(CRED_ID, TENANT_A)
        b = _azure_cred('other-id', TENANT_B)
        assert select_azure_credential([a, b], tenant=TENANT_B) is b

    def test_tenant_none_errors(self, capsys):
        creds = [_azure_cred(CRED_ID, TENANT_A)]
        with pytest.raises(SystemExit):
            select_azure_credential(creds, tenant=TENANT_B)
        err = capsys.readouterr().err
        assert CRED_ID in err
        assert TENANT_A in err

    def test_tenant_still_ambiguous_errors(self, capsys):
        creds = [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_A)]
        with pytest.raises(SystemExit) as exc:
            select_azure_credential(creds, tenant=TENANT_A)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert '--credential' in err
        assert CRED_ID in err
        assert 'other-id' in err

    def test_credential_unknown_errors(self, capsys):
        creds = [_azure_cred(CRED_ID, TENANT_A)]
        with pytest.raises(SystemExit) as exc:
            select_azure_credential(creds, credential='missing-uuid')
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert 'missing-uuid' in err


class TestAzureNoCreds:

    def test_no_creds_message_exit_zero(self):
        result = _invoke(_sdk([]))
        assert result.exit_code == 0
        assert f'No Azure credentials found for account {ACCOUNT}' in result.output


class TestAzureCLIPath:

    def test_single_cred_writes_unique_file_and_logs_in(self, tmp_path, monkeypatch):
        frozen = datetime(2026, 9, 16, 15, 30, 45, tzinfo=timezone.utc)
        monkeypatch.setattr(
            'praetorian_cli.handlers.access.datetime',
            SimpleNamespace(now=lambda tz=None: frozen),
        )
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)

        sdk = _sdk([_azure_cred()], response=_token_response())
        result = _invoke(sdk)
        assert result.exit_code == 0, result.output

        expected = tmp_path / '.azure' / f'client-{CRED_ID}-20260916T153045Z.json'
        assert expected.is_file()
        data = json.loads(expected.read_text())
        assert data == [{
            'client_id': CLIENT_ID,
            'tenant': TENANT_A,
            'client_assertion': ASSERTION,
        }]
        assert oct(expected.stat().st_mode & 0o777) == '0o600'
        assert not (tmp_path / '.azure' / 'service_principal_entries.json').exists()

        assert login_calls == [(CLIENT_ID, TENANT_A, ASSERTION)]
        assert str(expected) in result.output
        assert sdk.keychain.assumed == [ACCOUNT]
        assert sdk.credentials.get_calls, 'broker should have been called'
        call = sdk.credentials.get_calls[0]
        assert call['credential_id'] == CRED_ID
        assert call['category'] == 'env-integration'
        assert call['type'] == 'azure'
        assert call['format'] == 'token'

    def test_multi_without_flags_does_not_login_or_write(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk(
            [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_B)],
            response=_token_response(),
        )
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert CRED_ID in result.output
        assert TENANT_A in result.output
        assert not login_calls
        azure_dir = tmp_path / '.azure'
        if azure_dir.exists():
            assert list(azure_dir.iterdir()) == []

    def test_empty_credential_value_errors_and_writes_nothing(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk([_azure_cred()], response={'credentialValue': {}})
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert not login_calls
        assert list(tmp_path.rglob('*.json')) == []

    def test_tenant_flag_selects_matching_credential(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk(
            [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_B)],
            response=_token_response(tenant=TENANT_B),
        )
        result = _invoke(sdk, '--tenant', TENANT_B)
        assert result.exit_code == 0, result.output
        assert sdk.credentials.get_calls[0]['credential_id'] == 'other-id'
        assert login_calls == [(CLIENT_ID, TENANT_B, ASSERTION)]

    def test_credential_flag_selects_matching_uuid(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk(
            [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_B)],
            response=_token_response(),
        )
        result = _invoke(sdk, '--credential', 'other-id')
        assert result.exit_code == 0, result.output
        assert sdk.credentials.get_calls[0]['credential_id'] == 'other-id'
        assert login_calls == [(CLIENT_ID, TENANT_A, ASSERTION)]

    def test_tenant_still_ambiguous_via_cli(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk(
            [_azure_cred(CRED_ID, TENANT_A), _azure_cred('other-id', TENANT_A)],
            response=_token_response(),
        )
        result = _invoke(sdk, '--tenant', TENANT_A)
        assert result.exit_code != 0
        assert '--credential' in result.output
        assert not login_calls
        assert list(tmp_path.rglob('*.json')) == []

    def test_credential_unknown_via_cli(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        sdk = _sdk([_azure_cred()], response=_token_response())
        result = _invoke(sdk, '--credential', 'missing-uuid')
        assert result.exit_code != 0
        assert 'missing-uuid' in result.output
        assert not login_calls
        assert list(tmp_path.rglob('*.json')) == []

    def test_unsafe_prefix_errors_and_writes_nothing(self, tmp_path, monkeypatch):
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        account = 'chariot+../evil@praetorian.com'
        sdk = FakeSdk(FakeCredentials([_azure_cred()], response=_token_response()),
                      account=account)
        result = _invoke(sdk, '--account', account)
        assert result.exit_code != 0
        assert not login_calls
        assert list(tmp_path.rglob('*.json')) == []



    def test_same_second_collision_does_not_traceback(self, tmp_path, monkeypatch):
        frozen = datetime(2026, 9, 16, 15, 30, 45, tzinfo=timezone.utc)
        monkeypatch.setattr(
            'praetorian_cli.handlers.access.datetime',
            SimpleNamespace(now=lambda tz=None: frozen),
        )
        login_calls = _patch_azure_fs(monkeypatch, tmp_path)
        dest = tmp_path / '.azure' / f'client-{CRED_ID}-20260916T153045Z.json'
        dest.parent.mkdir()
        dest.write_text('pre-existing')

        sdk = _sdk([_azure_cred()], response=_token_response())
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'retry' in result.output.lower()
        assert 'Traceback' not in result.output
        assert not login_calls
        assert dest.read_text() == 'pre-existing'

    def test_failed_az_login_unlinks_sp_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'praetorian_cli.handlers.access.Path.home',
            lambda *args, **kwargs: tmp_path,
        )
        monkeypatch.setattr(
            'praetorian_cli.handlers.access.run_az_login',
            lambda *a, **k: (_ for _ in ()).throw(
                click.ClickException('az login failed')
            ),
        )
        sdk = _sdk([_azure_cred()], response=_token_response())
        result = _invoke(sdk)
        assert result.exit_code != 0
        azure_dir = tmp_path / '.azure'
        json_files = list(azure_dir.glob('*.json')) if azure_dir.exists() else []
        assert json_files == []


class TestRunAzLogin:

    def test_invokes_az_login(self, monkeypatch):
        from praetorian_cli.handlers.access import run_az_login

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout='', stderr='')

        monkeypatch.setattr('praetorian_cli.handlers.access.subprocess.run', fake_run)
        run_az_login(CLIENT_ID, TENANT_A, ASSERTION)
        assert calls == [[
            'az', 'login', '--service-principal',
            '-u', CLIENT_ID, '-t', TENANT_A, '--federated-token', ASSERTION,
        ]]

    def test_missing_az_raises_click_exception(self, monkeypatch):
        from praetorian_cli.handlers.access import run_az_login

        def fake_run(cmd, **kwargs):
            raise FileNotFoundError('az')

        monkeypatch.setattr('praetorian_cli.handlers.access.subprocess.run', fake_run)
        with pytest.raises(click.ClickException) as exc:
            run_az_login(CLIENT_ID, TENANT_A, ASSERTION)
        assert 'install' in str(exc.value).lower()
        assert 'az' in str(exc.value).lower()

    def test_nonzero_az_raises_click_exception(self, monkeypatch):
        from praetorian_cli.handlers.access import run_az_login

        monkeypatch.setattr(
            'praetorian_cli.handlers.access.subprocess.run',
            lambda *a, **k: SimpleNamespace(returncode=1, stdout='', stderr='login failed'),
        )
        with pytest.raises(click.ClickException):
            run_az_login(CLIENT_ID, TENANT_A, ASSERTION)

    def test_az_error_redacts_assertion(self, monkeypatch):
        from praetorian_cli.handlers.access import run_az_login

        monkeypatch.setattr(
            'praetorian_cli.handlers.access.subprocess.run',
            lambda *a, **k: SimpleNamespace(
                returncode=1,
                stdout='',
                stderr=f'AADSTS70021: {ASSERTION} is invalid',
            ),
        )
        with pytest.raises(click.ClickException) as exc:
            run_az_login(CLIENT_ID, TENANT_A, ASSERTION)
        assert ASSERTION not in str(exc.value)
