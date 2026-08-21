import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
import praetorian_cli.handlers.purge  # noqa: F401  (registers the purge commands)
import praetorian_cli.handlers.tenant  # noqa: F401  (registers the tenant commands)


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


class TestPurgeAsset:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_purge_asset_force(self):
        self.sdk.assets.purge.return_value = {'purged': 5}
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#old.com', '--force',
        ])
        assert result.exit_code == 0
        self.sdk.assets.purge.assert_called_once_with('#asset#old.com')

    def test_purge_asset_confirmed(self):
        self.sdk.assets.purge.return_value = {'purged': 3}
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#old.com',
        ], input='y\n')
        assert result.exit_code == 0
        self.sdk.assets.purge.assert_called_once()

    def test_purge_asset_cancelled(self):
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#old.com',
        ], input='n\n')
        assert result.exit_code == 0
        self.sdk.assets.purge.assert_not_called()
        assert 'cancelled' in result.output.lower()

    def test_purge_asset_dry_run(self):
        self.sdk.assets.list.return_value = (
            [{'key': '#asset#old.com#1'}, {'key': '#asset#old.com#2'}], None)
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#old.com', '--dry-run',
        ])
        assert result.exit_code == 0
        self.sdk.assets.purge.assert_not_called()
        assert '2 asset(s) would be purged' in result.output

    def test_purge_asset_dry_run_empty(self):
        self.sdk.assets.list.return_value = ([], None)
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#nothing', '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'no matching' in result.output.lower()

    def test_purge_asset_empty_filter_rejected(self):
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '  ', '--force',
        ])
        assert result.exit_code != 0
        self.sdk.assets.purge.assert_not_called()

    def test_purge_asset_backend_error(self):
        self.sdk.assets.purge.side_effect = Exception('403 Forbidden')
        result = _invoke(self.runner, self.sdk, [
            'purge', 'asset', '--filter', '#asset#x', '--force',
        ])
        assert 'ERROR' in result.output or result.exit_code != 0


class TestPurgeRisk:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_purge_risk_force(self):
        self.sdk.risks.purge.return_value = {'purged': 10}
        result = _invoke(self.runner, self.sdk, [
            'purge', 'risk', '--filter', '#risk#old.com', '--force',
        ])
        assert result.exit_code == 0
        self.sdk.risks.purge.assert_called_once_with('#risk#old.com')

    def test_purge_risk_dry_run(self):
        self.sdk.risks.list.return_value = (
            [{'key': '#risk#old.com#CVE-1'}], None)
        result = _invoke(self.runner, self.sdk, [
            'purge', 'risk', '--filter', '#risk#old.com', '--dry-run',
        ])
        assert result.exit_code == 0
        self.sdk.risks.purge.assert_not_called()
        assert '1 risk(s) would be purged' in result.output

    def test_purge_risk_cancelled(self):
        result = _invoke(self.runner, self.sdk, [
            'purge', 'risk', '--filter', '#risk#old.com',
        ], input='n\n')
        assert result.exit_code == 0
        self.sdk.risks.purge.assert_not_called()


class TestPurgeSeed:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_purge_seed_force(self):
        self.sdk.seeds.purge.return_value = {'purged': 2}
        result = _invoke(self.runner, self.sdk, [
            'purge', 'seed', '--filter', '#asset#old.com', '--force',
        ])
        assert result.exit_code == 0
        self.sdk.seeds.purge.assert_called_once_with('#asset#old.com')

    def test_purge_seed_dry_run(self):
        self.sdk.seeds.list.return_value = (
            [{'key': '#asset#old.com#old.com'}], None)
        result = _invoke(self.runner, self.sdk, [
            'purge', 'seed', '--filter', '#asset#old.com', '--dry-run',
        ])
        assert result.exit_code == 0
        self.sdk.seeds.purge.assert_not_called()


class TestTenantDelete:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_tenant_delete_with_force(self):
        self.sdk.accounts.delete_tenant.return_value = {'status': 'initiated'}
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'delete',
            '--email', 'customer@acme.com',
            '--confirm-name', 'customer@acme.com',
            '--force',
        ])
        assert result.exit_code == 0
        self.sdk.accounts.delete_tenant.assert_called_once_with('customer@acme.com')

    def test_tenant_delete_with_confirmation(self):
        self.sdk.accounts.delete_tenant.return_value = {'status': 'initiated'}
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'delete',
            '--email', 'customer@acme.com',
            '--confirm-name', 'customer@acme.com',
        ], input='y\n')
        assert result.exit_code == 0
        self.sdk.accounts.delete_tenant.assert_called_once()

    def test_tenant_delete_cancelled(self):
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'delete',
            '--email', 'customer@acme.com',
            '--confirm-name', 'customer@acme.com',
        ], input='n\n')
        assert result.exit_code == 0
        self.sdk.accounts.delete_tenant.assert_not_called()
        assert 'cancelled' in result.output.lower()

    def test_tenant_delete_name_mismatch(self):
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'delete',
            '--email', 'customer@acme.com',
            '--confirm-name', 'wrong@acme.com',
            '--force',
        ])
        assert result.exit_code != 0
        self.sdk.accounts.delete_tenant.assert_not_called()

    def test_tenant_delete_backend_error(self):
        self.sdk.accounts.delete_tenant.side_effect = Exception('404 Not found')
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'delete',
            '--email', 'customer@acme.com',
            '--confirm-name', 'customer@acme.com',
            '--force',
        ])
        assert 'ERROR' in result.output or result.exit_code != 0


class TestTenantStatus:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()

    def test_tenant_status(self):
        self.sdk.accounts.get_tenant_deletion.return_value = {'status': 'completed'}
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'status', 'del-123',
        ])
        assert result.exit_code == 0
        self.sdk.accounts.get_tenant_deletion.assert_called_once_with('del-123')

    def test_tenant_status_backend_error(self):
        self.sdk.accounts.get_tenant_deletion.side_effect = Exception('404 Not found')
        result = _invoke(self.runner, self.sdk, [
            'tenant', 'status', 'del-123',
        ])
        assert 'ERROR' in result.output or result.exit_code != 0


class TestPurgeSdkMethods:
    """Test the SDK purge methods themselves."""

    def test_assets_purge(self):
        from praetorian_cli.sdk.entities.assets import Assets
        api = MagicMock()
        api.post.return_value = {'purged': 5}
        assets = Assets(api)
        result = assets.purge('#asset#old.com')
        api.post.assert_called_once_with('asset/purge', dict(filter='#asset#old.com'))
        assert result == {'purged': 5}

    def test_risks_purge(self):
        from praetorian_cli.sdk.entities.risks import Risks
        api = MagicMock()
        api.post.return_value = {'purged': 3}
        risks = Risks(api)
        result = risks.purge('#risk#old.com')
        api.post.assert_called_once_with('risk/purge', dict(filter='#risk#old.com'))

    def test_seeds_purge(self):
        from praetorian_cli.sdk.entities.seeds import Seeds
        api = MagicMock()
        api.post.return_value = {'purged': 1}
        seeds = Seeds(api)
        result = seeds.purge('#asset#old.com')
        api.post.assert_called_once_with('seed/purge', dict(filter='#asset#old.com'))

    def test_accounts_delete_tenant(self):
        from praetorian_cli.sdk.entities.accounts import Accounts
        api = MagicMock()
        api.post.return_value = {'status': 'initiated'}
        accounts = Accounts(api)
        result = accounts.delete_tenant('customer@acme.com')
        api.post.assert_called_once_with('account/deletion', dict(email='customer@acme.com'))

    def test_accounts_get_tenant_deletion(self):
        from praetorian_cli.sdk.entities.accounts import Accounts
        api = MagicMock()
        api.get.return_value = {'status': 'completed'}
        accounts = Accounts(api)
        result = accounts.get_tenant_deletion('del-123')
        api.get.assert_called_once_with('account/deletion/del-123')
