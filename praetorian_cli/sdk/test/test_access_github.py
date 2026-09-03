import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.access import access


class FakeKeychain:
    def __init__(self, account='someone@example.com'):
        self.account = account


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


def _sdk(integrations, **cred_kwargs):
    return FakeSdk(FakeIntegrations(integrations), FakeCredentials(**cred_kwargs))


def _invoke(sdk, *args):
    return CliRunner().invoke(access, ['github', *args], obj=sdk)


class TestAccessCLIWiring:

    def test_github_subcommand_registered(self):
        assert 'github' in access.commands

    def test_github_help_lists_flags(self):
        result = CliRunner().invoke(access, ['github', '--help'])
        assert result.exit_code == 0
        assert '--org' in result.output
        assert '--format' in result.output
        assert 'token' in result.output
        assert 'env' in result.output

    def test_no_account_flag(self):
        """The account comes from the top-level guard --account, not this command."""
        params = [p.name for p in access.commands['github'].params]
        assert 'account' not in params


class TestGithubRetrieval:

    def test_no_integrations(self):
        result = _invoke(_sdk([]))
        assert result.exit_code != 0
        assert 'No GitHub integrations' in result.output

    def test_app_token_printed_default_format(self):
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghs_abc123'}})
        result = _invoke(sdk)
        assert result.exit_code == 0, result.output
        assert 'ghs_abc123' in result.output
        assert 'export' not in result.output

    def test_app_token_env_format(self):
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghs_abc123'}})
        result = _invoke(sdk, '--format', 'env')
        assert result.exit_code == 0, result.output
        assert 'export GITHUB_TOKEN=ghs_abc123' in result.output
        assert 'export GH_TOKEN=ghs_abc123' in result.output

    def test_env_format_quotes_hostile_token(self):
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghs_x; touch pwned'}})
        result = _invoke(sdk, '--format', 'env')
        assert result.exit_code == 0, result.output
        assert "export GITHUB_TOKEN='ghs_x; touch pwned'" in result.output

    def test_forbidden_403_emits_friendly_message(self):
        sdk = _sdk([_github_integration()],
                   raise_exc=Exception('[403] Request failed\nError: unauthorized'))
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'Guard denied the request' in result.output
        assert 'github.com/acme-inc' in result.output

    def test_empty_token_skipped(self):
        sdk = _sdk([_github_integration()], response={'credentialValue': {}})
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'broker returned no token' in result.output

    def test_non_string_token_rejected(self):
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': {'nested': 'oops'}}})
        result = _invoke(sdk)
        assert result.exit_code != 0
        assert 'broker returned no token' in result.output

    def test_static_pat_is_passed_through(self):
        """Lifecycle enforcement lives in Guard; the CLI no longer duplicates it."""
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghp_classic'}})
        result = _invoke(sdk)
        assert result.exit_code == 0, result.output
        assert 'ghp_classic' in result.output

    def test_broker_request_shape(self):
        """Lock in the request shape the github broker handler actually accepts.

        Github integrations store their secret directly on the Account record
        keyed by the integration's own key (see
        backend/pkg/services/account/integration_utils.go), not as a separate
        Credential entity with a HAS_CREDENTIAL edge. So the broker resolves
        github via by-target with the integration key as CredentialID, not via
        from-parent (which would walk the graph for a non-existent Credential).
        """
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghs_ok'}})
        _invoke(sdk)
        assert sdk.credentials.calls, 'broker should have been called'
        call = sdk.credentials.calls[0]
        assert call['resolution'] == 'by-target'
        assert call['credential_id'] == _github_integration()['key']
        assert call['type'] == 'github'
        assert call['format'] == ['token']


class TestOrgSelection:

    def _multi(self, **cred_kwargs):
        return _sdk([_github_integration('https://github.com/acme-inc'),
                     _github_integration('https://github.com/globex')],
                    **cred_kwargs)

    def test_single_integration_needs_no_org(self):
        sdk = _sdk([_github_integration()],
                   response={'credentialValue': {'github': 'ghs_ok'}})
        result = _invoke(sdk)
        assert result.exit_code == 0, result.output
        assert 'ghs_ok' in result.output

    def test_multiple_without_org_errors(self):
        result = _invoke(self._multi(response={'credentialValue': {'github': 'ghs_ok'}}))
        assert result.exit_code != 0
        assert 'more than one GitHub integration' in result.output
        # The error lists what the user can pick from.
        assert 'acme-inc' in result.output
        assert 'globex' in result.output
        # No token leaks when the selection is ambiguous.
        assert 'ghs_ok' not in result.output

    @pytest.mark.parametrize('org', ['globex', 'GLOBEX', 'https://github.com/globex'])
    def test_org_selects_matching_integration(self, org):
        sdk = self._multi(response={'credentialValue': {'github': 'ghs_ok'}})
        result = _invoke(sdk, '--org', org)
        assert result.exit_code == 0, result.output
        assert 'ghs_ok' in result.output
        assert sdk.credentials.calls[0]['credential_id'].endswith('globex')

    def test_org_no_match_errors(self):
        result = _invoke(self._multi(response={'credentialValue': {'github': 'ghs_ok'}}),
                         '--org', 'initech')
        assert result.exit_code != 0
        assert 'No GitHub integration matching' in result.output
        assert 'acme-inc' in result.output

    def test_only_one_broker_call_for_multiple_integrations(self):
        sdk = self._multi(response={'credentialValue': {'github': 'ghs_ok'}})
        _invoke(sdk, '--org', 'acme-inc')
        assert len(sdk.credentials.calls) == 1
