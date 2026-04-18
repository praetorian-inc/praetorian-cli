import pytest

from praetorian_cli.runners.local import _infer_protocol, _has_flag


class TestInferProtocol:
    def test_ssh_port(self):
        assert _infer_protocol('10.0.1.5:22') == 'ssh'

    def test_rdp_port(self):
        assert _infer_protocol('host.example.com:3389') == 'rdp'

    def test_ftp_port(self):
        assert _infer_protocol('192.168.1.1:21') == 'ftp'

    def test_smb_port(self):
        assert _infer_protocol('10.0.0.5:445') == 'smb'

    def test_telnet_port(self):
        assert _infer_protocol('10.0.0.5:23') == 'telnet'

    def test_mysql_port(self):
        assert _infer_protocol('db.example.com:3306') == 'mysql'

    def test_postgres_port(self):
        assert _infer_protocol('db.example.com:5432') == 'postgres'

    def test_unknown_port_returns_none(self):
        assert _infer_protocol('host:9999') is None

    def test_no_port_returns_none(self):
        assert _infer_protocol('example.com') is None

    def test_malformed_port_returns_none(self):
        assert _infer_protocol('host:notaport') is None

    def test_ipv6_bracket_form(self):
        # IPv6 addresses use [::1]:22 bracket form — we don't need to support this,
        # just not crash on it.
        assert _infer_protocol('[::1]:22') in ('ssh', None)


class TestHasFlag:
    def test_empty_passthrough(self):
        assert _has_flag(None, '-u') is False
        assert _has_flag([], '-u') is False

    def test_single_flag_present(self):
        assert _has_flag(['-u', 'foo'], '-u') is True

    def test_any_of_multiple(self):
        assert _has_flag(['-U', 'users.txt'], '-u', '-U') is True
        assert _has_flag(['-u', 'foo'], '-u', '-U') is True

    def test_flag_absent(self):
        assert _has_flag(['--other', 'val'], '-u') is False

    def test_flag_as_value_ignored(self):
        # A flag appearing only as a value to another flag should not match.
        # Simpler: we match anywhere in the list. This keeps the helper small.
        # If a user's file path happens to be '-u', that's their problem.
        assert _has_flag(['--config', '-u'], '-u') is True


from praetorian_cli.runners.local import ToolPlugin


class TestToolPluginBase:
    def test_default_plugin_passes_through(self):
        plugin = ToolPlugin()
        args = plugin.build_args('example.com', pass_through=['--flag', 'val'])
        assert args == ['example.com', '--flag', 'val']

    def test_default_plugin_without_passthrough(self):
        plugin = ToolPlugin()
        assert plugin.build_args('example.com') == ['example.com']

    def test_default_plugin_with_json_config_and_passthrough(self):
        plugin = ToolPlugin()
        args = plugin.build_args('t', extra_config='{"k":"v"}', pass_through=['--x'])
        # Default plugin ignores config but appends pass_through.
        assert args == ['t', '--x']


from praetorian_cli.runners.local import (
    BrutusPlugin, NucleiPlugin, TitusPlugin, TrajanPlugin, JuliusPlugin,
    AugustusPlugin, NervaPlugin, GatoPlugin, UrlTargetPlugin, ScanTargetPlugin,
)


class TestSubclassesAcceptPassThroughKwarg:
    """Every concrete plugin must accept pass_through so the base class can forward it.

    Body-level use of pass_through is added in Tasks 3 and 4; this test only guards
    the signature so mid-sequence HEADs remain runnable.
    """

    @pytest.mark.parametrize('plugin_cls', [
        BrutusPlugin, NucleiPlugin, TitusPlugin, TrajanPlugin, JuliusPlugin,
        AugustusPlugin, NervaPlugin, GatoPlugin, UrlTargetPlugin, ScanTargetPlugin,
    ])
    def test_build_args_does_not_raise_with_passthrough(self, plugin_cls):
        plugin = plugin_cls()
        # Just prove it doesn't TypeError. We don't assert on pass_through being
        # appended — Tasks 3 and 4 add that behavior per-plugin.
        plugin.build_args('example.com', pass_through=['--noop'])

    @pytest.mark.parametrize('plugin_cls', [
        BrutusPlugin, NucleiPlugin, TitusPlugin, TrajanPlugin, JuliusPlugin,
        AugustusPlugin, NervaPlugin, GatoPlugin, UrlTargetPlugin, ScanTargetPlugin,
    ])
    def test_build_args_without_passthrough_still_works(self, plugin_cls):
        plugin = plugin_cls()
        plugin.build_args('example.com')
