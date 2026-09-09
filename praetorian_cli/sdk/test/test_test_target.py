import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from click.core import ParameterSource
from click.testing import CliRunner

import praetorian_cli.handlers.test as test_handler
import praetorian_cli.main as cli_main
from praetorian_cli.sdk.test import utils


@pytest.mark.parametrize(
    ("profile", "account"),
    [
        (None, "account-123"),
        ("", "account-123"),
        ("United States", None),
        ("United States", ""),
    ],
)
def test_setup_chariot_requires_explicit_account(profile, account):
    with patch.object(utils, "Keychain") as keychain, patch.object(utils, "Chariot") as chariot:
        with pytest.raises(ValueError, match="profile and account"):
            utils.setup_chariot(profile, account)

    keychain.assert_not_called()
    chariot.assert_not_called()


def test_setup_chariot_requires_both_explicit_arguments():
    with patch.object(utils, "Keychain") as keychain, patch.object(utils, "Chariot") as chariot:
        with pytest.raises(TypeError):
            utils.setup_chariot()

    keychain.assert_not_called()
    chariot.assert_not_called()


def test_setup_chariot_propagates_selected_account_without_environment_fallback(monkeypatch):
    selected_keychain = SimpleNamespace(profile="United States", account="account-123")
    selected_chariot = object()
    monkeypatch.setenv("CHARIOT_TEST_PROFILE", "other-profile")
    monkeypatch.setenv("CHARIOT_TEST_ACCOUNT", "other-account")

    with patch.object(utils, "Keychain", return_value=selected_keychain) as keychain, \
         patch.object(utils, "Chariot", return_value=selected_chariot) as chariot:
        result = utils.setup_chariot("United States", "account-123")

    assert result is selected_chariot
    keychain.assert_called_once_with(profile="United States", account="account-123")
    chariot.assert_called_once_with(selected_keychain)


def test_setup_chariot_rejects_mismatched_target_before_sdk_construction():
    mismatched_keychain = SimpleNamespace(profile="United States", account="other-account")

    with patch.object(utils, "Keychain", return_value=mismatched_keychain), \
         patch.object(utils, "Chariot") as chariot:
        with pytest.raises(ValueError, match="does not match"):
            utils.setup_chariot("United States", "account-123")

    chariot.assert_not_called()


def test_selected_test_target_reads_exact_handler_environment(monkeypatch):
    monkeypatch.setenv("CHARIOT_TEST_PROFILE", "Selected Profile")
    monkeypatch.setenv("CHARIOT_TEST_ACCOUNT", "selected-account")

    assert utils.selected_test_target() == ("Selected Profile", "selected-account")


@pytest.mark.parametrize(
    ("profile", "account"),
    [
        (None, None),
        ("Selected Profile", None),
        (None, "selected-account"),
        (" ", "selected-account"),
        ("Selected Profile", " selected-account"),
    ],
)
def test_selected_test_target_rejects_missing_partial_or_malformed_before_sdk(
    monkeypatch,
    profile,
    account,
):
    for name, value in (
        ("CHARIOT_TEST_PROFILE", profile),
        ("CHARIOT_TEST_ACCOUNT", account),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with patch.object(utils, "Keychain") as keychain, \
         patch.object(utils, "Chariot") as chariot, \
         patch("praetorian_cli.sdk.keychain.requests.get") as network:
        with pytest.raises(ValueError, match="profile and account"):
            utils.selected_test_target()

    keychain.assert_not_called()
    chariot.assert_not_called()
    network.assert_not_called()


def test_existing_setup_class_reaches_keychain_with_selected_target(monkeypatch):
    from praetorian_cli.sdk.test.test_seed import TestSeed

    monkeypatch.setenv("CHARIOT_TEST_PROFILE", "Selected Profile")
    monkeypatch.setenv("CHARIOT_TEST_ACCOUNT", "selected-account")
    selected_keychain = SimpleNamespace(profile="Selected Profile", account="selected-account")
    selected_chariot = object()

    with patch.object(utils, "Keychain", return_value=selected_keychain) as keychain, \
         patch.object(utils, "Chariot", return_value=selected_chariot) as chariot:
        instance = TestSeed()
        instance.setup_class()

    assert instance.sdk is selected_chariot
    keychain.assert_called_once_with(profile="Selected Profile", account="selected-account")
    chariot.assert_called_once_with(selected_keychain)


def test_z_cli_helpers_forward_confirmed_target_as_inert_argv(monkeypatch):
    from praetorian_cli.sdk.test import test_z_cli

    confirmed_profile = "Selected Profile; $(profile-command)"
    confirmed_account = "selected+account;$(account-command)@example.com"
    configured_default = "configured-default@example.com"
    monkeypatch.setenv(utils.TEST_PROFILE_ENV, confirmed_profile)
    monkeypatch.setenv(utils.TEST_ACCOUNT_ENV, confirmed_account)
    sdk = SimpleNamespace(
        keychain=SimpleNamespace(
            profile=confirmed_profile,
            account=configured_default,
        )
    )
    child = Mock(
        side_effect=[
            SimpleNamespace(returncode=0, stdout='{"items": []}', stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
    )

    with patch.object(test_z_cli, "setup_chariot", return_value=sdk), patch.object(
        test_z_cli, "run", child
    ):
        test_case = test_z_cli.TestZCli()
        test_case.setup_class()
        assert test_case.run_json('list assets -f "#asset#alpha beta"') == {"items": []}
        test_case.verify('delete asset "#asset#alpha beta"')

    expected_prefix = [
        "guard",
        "--profile",
        confirmed_profile,
        "--account",
        confirmed_account,
    ]
    assert child.call_args_list[0].args[0] == expected_prefix + [
        "list",
        "assets",
        "-f",
        "#asset#alpha beta",
    ]
    assert child.call_args_list[1].args[0] == expected_prefix + [
        "delete",
        "asset",
        "#asset#alpha beta",
    ]
    for call in child.call_args_list:
        assert call.kwargs.get("shell", False) is False


@pytest.mark.parametrize(
    ("method", "command"),
    [
        ("run_json", "list assets"),
        ("verify", "delete asset target"),
    ],
)
def test_z_cli_helpers_fail_closed_without_confirmed_target(method, command):
    from praetorian_cli.sdk.test import test_z_cli

    child = Mock()
    test_case = test_z_cli.TestZCli()
    test_case.sdk = SimpleNamespace(
        keychain=SimpleNamespace(profile="profile-default", account="account-default")
    )

    with patch.object(test_z_cli, "run", child):
        with pytest.raises(ValueError, match="confirmed profile and account"):
            getattr(test_case, method)(command)

    child.assert_not_called()


def test_test_handler_callback_stays_below_review_limit():
    callback = inspect.unwrap(test_handler.test.callback)

    assert len(inspect.getsourcelines(callback)[0]) < 50


def test_suite_risk_is_explicit_for_every_suite():
    expected = {
        "safe": (True, False, False, False, False),
        "coherence": (False, True, True, False, True),
        "cli": (False, True, True, False, True),
        "tui": (False, False, False, True, False),
    }

    assert set(test_handler.TEST_SUITES) == set(expected)
    for name, risk in expected.items():
        suite = test_handler.TEST_SUITES[name]
        assert suite.name == name
        assert (
            suite.local_safe,
            suite.live,
            suite.mutating,
            suite.tui,
            suite.requires_target,
        ) == risk
        assert suite.pytest_selector


def test_safe_suite_uses_an_explicit_keyless_selector():
    suite = test_handler.TEST_SUITES["safe"]

    assert suite.pytest_selector == ("-m", "not coherence and not cli and not tui")
    assert suite.local_safe is True
    assert suite.requires_target is False


# The Click layer is where the --profile default is injected, so the explicit-target
# gate can only be exercised through the public entry points. `guard` is the shipped
# console script (setup.cfg: guard = praetorian_cli.main:guard_main); under the legacy
# `praetorian` entry point the same command sits under the `chariot` group.
ENTRY_POINTS = [(cli_main.guard_main, []), (cli_main.main, ['chariot'])]
ENTRY_POINT_IDS = ['guard_main', 'main']


@pytest.fixture
def runner():
    return CliRunner()


def _coherence_argv(command_path, *root_options):
    return [*root_options, *command_path, 'test', '--suite', 'coherence']


def _invoke_gated(runner, entry_point, argv):
    """Drive the public CLI with the live-suite launcher armed to fail loudly.

    `--suite coherence` creates, mutates and deletes real entities in a real Guard
    account. Nothing here may reach subprocess.run, and the confirmation prompt --
    if the gate ever lets execution get that far -- is answered with a refusal.
    """
    with patch.object(
        test_handler.subprocess,
        'run',
        side_effect=AssertionError('a live, mutating suite was launched'),
    ) as run:
        result = runner.invoke(entry_point, argv, input='n\n')
    return result, run


@pytest.mark.parametrize(('entry_point', 'command_path'), ENTRY_POINTS, ids=ENTRY_POINT_IDS)
def test_coherence_suite_rejects_defaulted_profile(runner, entry_point, command_path):
    result, run = _invoke_gated(
        runner,
        entry_point,
        _coherence_argv(command_path, '--account', 'someone@example.com'),
    )

    assert result.exit_code == 2
    assert 'an explicit, unambiguous profile is required' in result.output
    run.assert_not_called()


@pytest.mark.parametrize(('entry_point', 'command_path'), ENTRY_POINTS, ids=ENTRY_POINT_IDS)
def test_coherence_suite_accepts_explicitly_passed_default_profile(runner, entry_point, command_path):
    result, run = _invoke_gated(
        runner,
        entry_point,
        _coherence_argv(
            command_path,
            '--profile',
            'United States',
            '--account',
            'someone@example.com',
        ),
    )

    assert 'Suite: coherence' in result.output
    assert 'Profile: United States' in result.output
    assert 'MUTATING' in result.output
    assert result.exit_code == 1
    run.assert_not_called()


@pytest.mark.parametrize(('entry_point', 'command_path'), ENTRY_POINTS, ids=ENTRY_POINT_IDS)
def test_coherence_suite_rejects_missing_target_entirely(runner, entry_point, command_path):
    result, run = _invoke_gated(runner, entry_point, _coherence_argv(command_path))

    assert result.exit_code == 2
    assert 'an explicit, unambiguous profile is required' in result.output
    assert 'unambiguous account' not in result.output
    run.assert_not_called()


@pytest.mark.parametrize(('entry_point', 'command_path'), ENTRY_POINTS, ids=ENTRY_POINT_IDS)
def test_coherence_suite_rejects_defaulted_account(runner, entry_point, command_path):
    result, run = _invoke_gated(
        runner,
        entry_point,
        _coherence_argv(command_path, '--profile', 'Canada'),
    )

    assert result.exit_code == 2
    assert 'an explicit, unambiguous account is required' in result.output
    run.assert_not_called()


@pytest.mark.parametrize(
    ('profile', 'account', 'label'),
    [
        ('', 'a@b.c', 'profile'),
        (' United States ', 'a@b.c', 'profile'),
        ('United States', '', 'account'),
    ],
    ids=['empty-profile', 'untrimmed-profile', 'empty-account'],
)
def test_coherence_suite_rejects_blank_or_untrimmed_explicit_values(runner, profile, account, label):
    result, run = _invoke_gated(
        runner,
        cli_main.guard_main,
        _coherence_argv([], '--profile', profile, '--account', account),
    )

    assert result.exit_code == 2
    assert f'an explicit, unambiguous {label} is required' in result.output
    run.assert_not_called()


@pytest.mark.parametrize(
    'argv',
    [['test'], ['test', '--suite', 'safe']],
    ids=['implicit-default', 'explicit-safe'],
)
def test_safe_suite_needs_no_explicit_target(runner, argv):
    with patch.object(test_handler.subprocess, 'run', return_value=Mock(returncode=0)) as run:
        result = runner.invoke(cli_main.guard_main, argv, input='n\n')

    assert result.exit_code == 0
    run.assert_called_once()
    assert 'explicit, unambiguous' not in result.output


def test_supplied_only_honours_commandline_and_environment_sources():
    assert cli_main.SUPPLIED_PARAMETER_SOURCES == (
        ParameterSource.COMMANDLINE,
        ParameterSource.ENVIRONMENT,
    )
    assert ParameterSource.DEFAULT not in cli_main.SUPPLIED_PARAMETER_SOURCES
    assert ParameterSource.DEFAULT_MAP not in cli_main.SUPPLIED_PARAMETER_SOURCES
    assert ParameterSource.PROMPT not in cli_main.SUPPLIED_PARAMETER_SOURCES
