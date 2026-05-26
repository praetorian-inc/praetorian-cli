import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.access import access, github, GITHUB_APP_TOKEN_PREFIX


class FakeKeychain:
    def __init__(self, account='someone@example.com'):
        self.account = account
        self.assumed = []

    def assume_role(self, account):
        self.assumed.append(account)


class FakeIntegrations:
    def __init__(self, items):
        self._items = items

    def list(self, name_filter='', offset=None, pages=100000):
        if name_filter:
            return [i for i in self._items if i.get('member') == name_filter], None
        return list(self._items), None


class FakeCredentials:
    def __init__(self, *, response=None, raise_exc=None):
        self._response = response
        self._raise = raise_exc
        self.calls = []

    def get(self, credential_id, category, type, format, **kwargs):
        self.calls.append({'credential_id': credential_id, 'category': category,
                           'type': type, 'format': format, **kwargs})
        if self._raise:
            raise self._raise
        return self._response


class FakeSdk:
    def __init__(self, integrations, credentials):
        self.keychain = FakeKeychain()
        self.integrations = integrations
        self.credentials = credentials


def _github_integration(url='https://github.com/acme-inc'):
    return {
        'key': f'#account#someone@example.com#github#{url}',
        'member': 'github',
        'name': 'someone@example.com',
        'value': url,
    }


def _invoke(sdk, *args):
    return CliRunner().invoke(access, ['github', *args], obj=sdk)


class TestAccessCLIWiring:

    def test_github_subcommand_registered(self):
        assert 'github' in access.commands

    def test_github_help_lists_flags(self):
        result = CliRunner().invoke(access, ['github', '--help'])
        assert result.exit_code == 0
        assert '--account' in result.output
        assert '--format' in result.output
        # The output choices wrap onto two lines under Click's formatter, so
        # match on the un-broken substring instead of the full bracketed form.
        assert 'token' in result.output
        assert 'env' in result.output


class TestGithubRetrieval:

    def test_no_integrations(self):
        sdk = FakeSdk(FakeIntegrations([]), FakeCredentials())
        result = _invoke(sdk)
        assert result.exit_code == 0
        assert 'No GitHub integrations' in result.output
        # When there's nothing to print, stdout stays empty.
        assert GITHUB_APP_TOKEN_PREFIX not in result.output

    def test_app_token_printed_default_format(self):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(response={'credentialValue': {'github': 'ghs_abc123'}}),
        )
        result = _invoke(sdk)
        assert result.exit_code == 0, result.output
        assert 'ghs_abc123' in result.output
        # Default format is bare token, not env-export lines.
        assert 'export' not in result.output

    def test_app_token_env_format(self):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(response={'credentialValue': {'github': 'ghs_abc123'}}),
        )
        result = _invoke(sdk, '--format', 'env')
        assert result.exit_code == 0, result.output
        assert 'export GITHUB_TOKEN=ghs_abc123' in result.output
        assert 'export GH_TOKEN=ghs_abc123' in result.output

    @pytest.mark.parametrize('token', ['ghp_classicPATvalue', 'github_pat_finegrained'])
    def test_pat_prefix_refused(self, token):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(response={'credentialValue': {'github': token}}),
        )
        result = _invoke(sdk)
        # Refused because no temporary token was retrieved -> non-zero exit.
        assert result.exit_code != 0
        assert 'Refusing token' in result.output
        assert token not in result.output  # nothing leaked to stdout

    def test_forbidden_403_emits_friendly_message(self):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(raise_exc=Exception('[403] Request failed\nError: unauthorized')),
        )
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'Guard denied the request' in result.output
        assert 'github.com/acme-inc' in result.output

    def test_empty_token_skipped(self):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(response={'credentialValue': {}}),
        )
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'broker returned no token' in result.output

    def test_broker_request_shape(self):
        """Lock in the only request shape the github broker handler routes."""
        fake_creds = FakeCredentials(response={'credentialValue': {'github': 'ghs_ok'}})
        sdk = FakeSdk(FakeIntegrations([_github_integration()]), fake_creds)
        _invoke(sdk)
        assert fake_creds.calls, 'broker should have been called'
        call = fake_creds.calls[0]
        assert call['resolution'] == 'from-parent'
        assert call['resource_key'] == _github_integration()['key']
        assert call['type'] == 'github'
        assert call['format'] == ['token']

    def test_keychain_assume_role_called(self):
        sdk = FakeSdk(
            FakeIntegrations([_github_integration()]),
            FakeCredentials(response={'credentialValue': {'github': 'ghs_ok'}}),
        )
        _invoke(sdk, '--account', 'override@example.com')
        assert sdk.keychain.assumed == ['override@example.com']
