from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.aegis  # noqa: F401 - registers aegis commands on chariot
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.sdk.entities.aegis import Aegis


PENDING_RAW = {
    'endpointId': 'endpoint-1',
    'account': 'customer@example.test',
    'kind': 'aegis',
    'metadata': {
        'version': '1.2.3',
        'hostname': 'sensor-1',
        'os': 'linux',
        'arch': 'amd64',
    },
    'createdAt': '2026-08-25T16:00:00Z',
    'expiresAt': '2026-08-25T16:10:00Z',
    'csr': 'SHOULD_NOT_LEAK',
    'cert': 'SHOULD_NOT_LEAK',
    'privateKey': 'SHOULD_NOT_LEAK',
}


class FakeAPI:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def post(self, path, body):
        self.calls.append({'path': path, 'body': body})
        response = self.responses.get(path, {})
        if isinstance(response, Exception):
            raise response
        return response


class FakeAegis:
    def __init__(self, inspect_response=None, approve_response=None, inspect_error=None, approve_error=None):
        self.inspect_response = inspect_response or PENDING_RAW
        self.approve_response = approve_response or {'status': 'approved'}
        self.inspect_error = inspect_error
        self.approve_error = approve_error
        self.calls = []

    def inspect_enrollment(self, user_code):
        self.calls.append(('inspect', user_code))
        if self.inspect_error:
            raise self.inspect_error
        return dict(self.inspect_response)

    def approve_enrollment(self, user_code):
        self.calls.append(('approve', user_code))
        if self.approve_error:
            raise self.approve_error
        return dict(self.approve_response)


class FakeSDK:
    def __init__(self, aegis):
        self.aegis = aegis


def test_inspect_enrollment_posts_user_code_only_and_normalizes_safe_fields():
    api = FakeAPI({'endpoint/enrollment/inspect': PENDING_RAW})

    pending = Aegis(api).inspect_enrollment(' abcd-efgh ')

    assert api.calls == [{
        'path': 'endpoint/enrollment/inspect',
        'body': {'userCode': 'abcd-efgh'},
    }]
    assert pending == {
        'endpoint_id': 'endpoint-1',
        'account': 'customer@example.test',
        'kind': 'aegis',
        'version': '1.2.3',
        'hostname': 'sensor-1',
        'os': 'linux',
        'arch': 'amd64',
        'created_at': '2026-08-25T16:00:00Z',
        'expires_at': '2026-08-25T16:10:00Z',
    }
    assert 'csr' not in pending
    assert 'cert' not in pending
    assert 'privateKey' not in pending


def test_approve_enrollment_posts_user_code_only():
    api = FakeAPI({'endpoint/enrollment/approve': {'status': 'approved'}})

    result = Aegis(api).approve_enrollment('ABCD-EFGH')

    assert api.calls == [{
        'path': 'endpoint/enrollment/approve',
        'body': {'userCode': 'ABCD-EFGH'},
    }]
    assert result == {'status': 'approved'}


@pytest.mark.parametrize('method', ['inspect_enrollment', 'approve_enrollment'])
def test_enrollment_methods_require_user_code(method):
    with pytest.raises(ValueError, match='user code is required'):
        getattr(Aegis(FakeAPI()), method)('  ')


def _invoke(fake_sdk, argv, input_text=''):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return CliRunner().invoke(chariot, argv, obj=obj, input=input_text, catch_exceptions=False)


def _invoke_debug(fake_sdk, argv):
    @click.group()
    @click.option('--debug', is_flag=True)
    @click.pass_context
    def root(ctx, debug):
        ctx.obj = {'keychain': MagicMock(), 'proxy': ''}

    root.add_command(chariot)
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=fake_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return CliRunner().invoke(root, ['--debug', 'chariot', *argv])


def test_cli_approve_enrollment_inspects_confirms_then_approves_without_leaking_material():
    fake_aegis = FakeAegis()

    result = _invoke(
        FakeSDK(fake_aegis),
        ['aegis', 'enrollment', 'approve', 'ABCD-EFGH'],
        input_text='y\n',
    )

    assert result.exit_code == 0
    assert fake_aegis.calls == [('inspect', 'ABCD-EFGH'), ('approve', 'ABCD-EFGH')]
    assert 'endpoint-1' in result.output
    assert 'customer@example.test' in result.output
    assert 'aegis' in result.output
    assert '1.2.3' in result.output
    assert 'sensor-1' in result.output
    assert 'linux/amd64' in result.output
    assert '2026-08-25T16:00:00Z' in result.output
    assert '2026-08-25T16:10:00Z' in result.output
    assert 'approved' in result.output.lower()
    assert 'SHOULD_NOT_LEAK' not in result.output
    assert 'csr' not in result.output.lower()
    assert 'cert' not in result.output.lower()
    assert 'private' not in result.output.lower()


def test_cli_approve_enrollment_cancel_does_not_approve():
    fake_aegis = FakeAegis()

    result = _invoke(
        FakeSDK(fake_aegis),
        ['aegis', 'enrollment', 'approve', 'ABCD-EFGH'],
        input_text='n\n',
    )

    assert result.exit_code == 0
    assert fake_aegis.calls == [('inspect', 'ABCD-EFGH')]
    assert 'Cancelled' in result.output


def test_cli_approval_error_maps_access_denied_to_actionable_message():
    fake_aegis = FakeAegis(
        inspect_error=Exception('[409] Request failed\nError: {"error":"access_denied"}')
    )

    result = _invoke(
        FakeSDK(fake_aegis),
        ['aegis', 'enrollment', 'approve', 'ABCD-EFGH', '--yes'],
    )

    assert result.exit_code != 0
    assert 'cannot be approved for this account' in result.output
    assert 'SHOULD_NOT_LEAK' not in result.output


@pytest.mark.parametrize(
    ('argv', 'error_field'),
    [
        (['aegis', 'enrollment', 'inspect', 'ABCD-EFGH'], 'inspect_error'),
        (['aegis', 'enrollment', 'approve', 'ABCD-EFGH', '--yes'], 'approve_error'),
    ],
)
def test_cli_enrollment_debug_preserves_original_exception(argv, error_field):
    cause = RuntimeError(f'unexpected {error_field}')
    fake_aegis = FakeAegis(**{error_field: cause})

    result = _invoke_debug(FakeSDK(fake_aegis), argv)

    assert result.exit_code == 1
    assert result.exception is cause
    assert 're-run with --debug for details' not in result.output
