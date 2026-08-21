import json
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.ad  # noqa: F401 - registers the 'ad' command group on import


def _invoke(runner, sdk, argv, **kwargs):
    """Invoke the CLI with a patched SDK factory.

    The `chariot` click group replaces `ctx.obj` with a `Chariot` instance,
    built lazily inside the group callback via `from praetorian_cli.sdk.chariot
    import Chariot`. We patch that source symbol so every instantiation yields
    our fake SDK. We also seed `ctx.obj` with the dict shape the group expects
    (`{'keychain', 'proxy'}`) so invocation doesn't blow up before the patch
    takes effect. (Mirrors the pattern used in test_schedule_cli.py.)
    """
    obj = {'keychain': MagicMock(), 'proxy': ''}
    chariot.is_debug = False
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, **kwargs)


def _make_sdk():
    sdk = MagicMock()
    return sdk


def _ad_results(*items):
    return (list(items), None)


class TestAdListObjects:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_list_objects_basic(self):
        self.sdk.ad.list_objects.return_value = _ad_results(
            {'key': '#aduser#contoso.local#S-1', 'name': 'admin'})
        result = _invoke(self.runner, self.sdk, ['ad', 'list-objects', 'user'])
        assert result.exit_code == 0
        self.sdk.ad.list_objects.assert_called_once_with(
            'user', domain=None, name_contains=None, pages=1)
        assert '#aduser#contoso.local#S-1' in result.output

    def test_list_objects_with_domain(self):
        self.sdk.ad.list_objects.return_value = _ad_results()
        result = _invoke(self.runner, self.sdk, [
            'ad', 'list-objects', 'computer', '--domain', 'contoso.local'
        ])
        assert result.exit_code == 0
        self.sdk.ad.list_objects.assert_called_once_with(
            'computer', domain='contoso.local', name_contains=None, pages=1)

    def test_list_objects_json_output(self):
        self.sdk.ad.list_objects.return_value = _ad_results(
            {'key': '#aduser#contoso.local#S-1', 'name': 'admin'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'list-objects', 'user', '--json'
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert 'data' in parsed

    def test_list_objects_sdk_error(self):
        self.sdk.ad.list_objects.side_effect = ValueError('Unknown type')
        result = _invoke(self.runner, self.sdk, ['ad', 'list-objects', 'badtype'])
        assert 'ERROR' in result.output or result.exit_code != 0


class TestAdGetObject:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_get_object_by_key(self):
        self.sdk.ad.get_object.return_value = _ad_results({'key': '#aduser#x#S-1'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'get-object', '--key', '#aduser#x#S-1'
        ])
        assert result.exit_code == 0
        self.sdk.ad.get_object.assert_called_once_with(key='#aduser#x#S-1', objectid=None, domain=None)

    def test_get_object_by_objectid(self):
        self.sdk.ad.get_object.return_value = _ad_results({'key': '#aduser#x#S-1'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'get-object', '--objectid', 'S-1-5-21', '--domain', 'contoso.local'
        ])
        assert result.exit_code == 0
        self.sdk.ad.get_object.assert_called_once_with(
            key=None, objectid='S-1-5-21', domain='contoso.local')

    def test_get_object_no_identifier_fails(self):
        result = _invoke(self.runner, self.sdk, ['ad', 'get-object'])
        assert 'ERROR' in result.output or result.exit_code != 0
        self.sdk.ad.get_object.assert_not_called()


class TestAdFindAttackPath:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_find_attack_path(self):
        self.sdk.ad.find_attack_path.return_value = _ad_results(
            {'key': 'path-node-1'}, {'key': 'path-node-2'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'find-attack-path',
            '--source', '#aduser#x#S-1',
            '--target', '#adgroup#x#S-2',
        ])
        assert result.exit_code == 0
        self.sdk.ad.find_attack_path.assert_called_once_with(
            source_key='#aduser#x#S-1', target_key='#adgroup#x#S-2',
            max_depth=5, shortest=1)

    def test_find_attack_path_json(self):
        self.sdk.ad.find_attack_path.return_value = _ad_results({'key': 'n1'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'find-attack-path',
            '--source', '#aduser#x#S-1',
            '--target', '#adgroup#x#S-2',
            '--json',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert 'data' in parsed


class TestAdWhoCanWhatCan:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_who_can(self):
        self.sdk.ad.who_can.return_value = _ad_results({'key': '#aduser#x#attacker'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'who-can', 'GenericAll',
            '--target', '#adgroup#x#DA',
        ])
        assert result.exit_code == 0
        self.sdk.ad.who_can.assert_called_once()

    def test_what_can(self):
        self.sdk.ad.what_can.return_value = _ad_results({'key': '#adcomputer#x#DC'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'what-can', 'GenericAll',
            '--source', '#aduser#x#attacker',
        ])
        assert result.exit_code == 0
        self.sdk.ad.what_can.assert_called_once()


class TestAdGroupCommands:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_group_members(self):
        self.sdk.ad.group_members.return_value = _ad_results({'key': '#aduser#x#S-1'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'group-members', '#adgroup#x#S-DA',
        ])
        assert result.exit_code == 0
        self.sdk.ad.group_members.assert_called_once_with(
            '#adgroup#x#S-DA', recursive=False, member_type=None, pages=1)

    def test_group_members_recursive(self):
        self.sdk.ad.group_members.return_value = _ad_results()
        result = _invoke(self.runner, self.sdk, [
            'ad', 'group-members', '#adgroup#x#S-DA', '--recursive',
        ])
        assert result.exit_code == 0
        self.sdk.ad.group_members.assert_called_once_with(
            '#adgroup#x#S-DA', recursive=True, member_type=None, pages=1)

    def test_group_memberships(self):
        self.sdk.ad.group_memberships.return_value = _ad_results({'key': '#adgroup#x#grp'})
        result = _invoke(self.runner, self.sdk, [
            'ad', 'group-memberships', '#aduser#x#S-1',
        ])
        assert result.exit_code == 0
        self.sdk.ad.group_memberships.assert_called_once_with(
            '#aduser#x#S-1', recursive=False, pages=1)


class TestAdSecurityQueries:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = _make_sdk()

    def test_kerberoastable_users(self):
        self.sdk.ad.kerberoastable_users.return_value = _ad_results({'key': 'svc-sql'})
        result = _invoke(self.runner, self.sdk, ['ad', 'kerberoastable-users'])
        assert result.exit_code == 0
        self.sdk.ad.kerberoastable_users.assert_called_once_with(domain=None, pages=1)

    def test_asreproastable_users(self):
        self.sdk.ad.asreproastable_users.return_value = _ad_results()
        result = _invoke(self.runner, self.sdk, [
            'ad', 'asreproastable-users', '--domain', 'corp.local'
        ])
        assert result.exit_code == 0
        self.sdk.ad.asreproastable_users.assert_called_once_with(domain='corp.local', pages=1)

    def test_unconstrained_delegation(self):
        self.sdk.ad.unconstrained_delegation.return_value = _ad_results({'key': 'DC01'})
        result = _invoke(self.runner, self.sdk, ['ad', 'unconstrained-delegation'])
        assert result.exit_code == 0

    def test_dcsync_principals(self):
        self.sdk.ad.dcsync_principals.return_value = _ad_results({'key': 'admin'})
        result = _invoke(self.runner, self.sdk, ['ad', 'dcsync-principals'])
        assert result.exit_code == 0
        self.sdk.ad.dcsync_principals.assert_called_once_with(
            domain_key=None, domain=None, pages=1)

    def test_tier_zero_objects(self):
        self.sdk.ad.tier_zero_objects.return_value = _ad_results({'key': 'DA-group'})
        result = _invoke(self.runner, self.sdk, ['ad', 'tier-zero-objects'])
        assert result.exit_code == 0

    def test_domains(self):
        self.sdk.ad.domains.return_value = _ad_results(
            {'key': '#addomain#contoso.local#contoso.local'})
        result = _invoke(self.runner, self.sdk, ['ad', 'domains'])
        assert result.exit_code == 0
        assert 'contoso.local' in result.output

    def test_domains_json(self):
        self.sdk.ad.domains.return_value = _ad_results(
            {'key': '#addomain#contoso.local#contoso.local', 'name': 'contoso.local'})
        result = _invoke(self.runner, self.sdk, ['ad', 'domains', '--json'])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed['data']) == 1
