from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.cli_decorators as cli_decorators
import praetorian_cli.handlers.script as script_handler
import praetorian_cli.handlers.test as test_handler
import praetorian_cli.main as cli_main
from praetorian_cli.sdk.keychain import Keychain as SdkKeychain


PROFILE = "United States"
ACCOUNT = "account-123"
CREDENTIAL_ENV = (
    "PRAETORIAN_CLI_USERNAME",
    "PRAETORIAN_CLI_PASSWORD",
    "PRAETORIAN_CLI_API_KEY_ID",
    "PRAETORIAN_CLI_API_KEY_SECRET",
    "PRAETORIAN_CLI_API",
    "PRAETORIAN_CLI_CLIENT_ID",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "BOTO_CONFIG",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "AWS_ROLE_SESSION_NAME",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
)
CREDENTIAL_FILE_ENV = (
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "BOTO_CONFIG",
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def guard_preconsent_sentinels():
    with (
        patch.object(
            cli_main,
            "Keychain",
            side_effect=AssertionError("Keychain constructed before consent"),
        ) as keychain,
        patch(
            "praetorian_cli.sdk.chariot.Chariot",
            side_effect=AssertionError("Chariot constructed before consent"),
        ) as chariot,
        patch.object(
            script_handler,
            "load_dynamic_commands",
            side_effect=AssertionError("dynamic commands loaded before consent"),
        ) as loader,
        patch.object(
            cli_decorators.requests,
            "get",
            side_effect=AssertionError("network used before consent"),
        ) as network,
        patch.object(
            SdkKeychain,
            "load",
            side_effect=AssertionError("Keychain loaded before consent"),
        ) as keychain_load,
        patch.object(
            SdkKeychain,
            "token",
            side_effect=AssertionError("token requested before consent"),
        ) as token,
    ):
        yield SimpleNamespace(
            keychain=keychain,
            chariot=chariot,
            loader=loader,
            network=network,
            keychain_load=keychain_load,
            token=token,
        )


def _chariot(profile=PROFILE, account=ACCOUNT):
    return SimpleNamespace(
        keychain=SimpleNamespace(profile=profile, account=account),
        proxy="http://localhost:8080",
    )


def _invoke(runner, argv, *, chariot=None, input=None, returncode=0, env=None):
    completed = SimpleNamespace(returncode=returncode)
    with patch.object(test_handler.subprocess, "run", return_value=completed) as run:
        result = runner.invoke(
            test_handler.test,
            argv,
            obj=chariot or _chariot(),
            input=input,
            env=env,
        )
    return result, run


def _guard_test_args(suite):
    return ["--profile", PROFILE, "--account", ACCOUNT, "test", "--suite", suite]


def _public_test_args(entry_point, suite, *, include_account=True):
    args = ["--profile", PROFILE]
    if include_account:
        args.extend(["--account", ACCOUNT])
    if entry_point is cli_main.main:
        args.append("chariot")
    return [*args, "test", "--suite", suite]


@pytest.mark.parametrize("entry_point", [cli_main.guard_main, cli_main.main])
@pytest.mark.parametrize(
    ("include_account", "input"),
    [(False, "y\n"), (True, "n\n"), (True, "")],
    ids=["missing-target", "refusal", "eof"],
)
def test_every_public_live_path_is_inert_before_consent(
    runner,
    guard_preconsent_sentinels,
    monkeypatch,
    tmp_path,
    entry_point,
    include_account,
    input,
):
    imported = tmp_path / "imported"
    (tmp_path / "sentinel.py").write_text(
        f"from pathlib import Path\nPath({str(imported)!r}).write_text('imported')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRAETORIAN_SCRIPTS_PATH", str(tmp_path))

    with patch.object(
        test_handler.subprocess,
        "run",
        side_effect=AssertionError("subprocess started before consent"),
    ) as run:
        result = runner.invoke(
            entry_point,
            _public_test_args(entry_point, "coherence", include_account=include_account),
            input=input,
        )

    assert result.exit_code != 0
    run.assert_not_called()
    assert not imported.exists()
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


@pytest.mark.parametrize("entry_point", [cli_main.guard_main, cli_main.main])
def test_every_public_live_path_propagates_confirmed_target_and_status(
    runner,
    guard_preconsent_sentinels,
    entry_point,
):
    completed = SimpleNamespace(returncode=5)
    with patch.object(test_handler.subprocess, "run", return_value=completed) as run:
        result = runner.invoke(
            entry_point,
            _public_test_args(entry_point, "coherence"),
            input="y\n",
        )

    assert result.exit_code == 5
    assert result.output.count("[y/N]") == 1
    assert result.output.count(f"Profile: {PROFILE}") == 1
    assert result.output.count(f"Account: {ACCOUNT}") == 1
    environment = run.call_args.kwargs["env"]
    assert environment["CHARIOT_TEST_PROFILE"] == PROFILE
    assert environment["CHARIOT_TEST_ACCOUNT"] == ACCOUNT
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


def test_guard_live_refusal_has_no_preconsent_side_effects(runner, guard_preconsent_sentinels):
    with patch.object(
        test_handler.subprocess,
        "run",
        side_effect=AssertionError("subprocess started before consent"),
    ) as run:
        result = runner.invoke(cli_main.guard_main, _guard_test_args("coherence"), input="n\n")

    assert result.exit_code != 0
    assert "coherence" in result.output
    assert PROFILE in result.output
    assert ACCOUNT in result.output
    run.assert_not_called()
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


def test_guard_live_missing_target_has_no_preconsent_side_effects(runner, guard_preconsent_sentinels):
    with patch.object(
        test_handler.subprocess,
        "run",
        side_effect=AssertionError("subprocess started without a target"),
    ) as run:
        result = runner.invoke(
            cli_main.guard_main,
            ["--profile", PROFILE, "test", "--suite", "coherence"],
            input="y\n",
        )

    assert result.exit_code != 0
    assert "account" in result.output.lower()
    run.assert_not_called()
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


def test_guard_live_acceptance_propagates_pytest_status_without_root_initialization(
    runner,
    guard_preconsent_sentinels,
):
    completed = SimpleNamespace(returncode=5)
    with patch.object(test_handler.subprocess, "run", return_value=completed) as run:
        result = runner.invoke(cli_main.guard_main, _guard_test_args("coherence"), input="y\n")

    assert result.exit_code == 5
    run.assert_called_once()
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


def test_guard_safe_suite_skips_root_initialization_and_remains_noninteractive(
    runner,
    guard_preconsent_sentinels,
):
    completed = SimpleNamespace(returncode=0)
    with (
        patch.object(test_handler.subprocess, "run", return_value=completed) as run,
        patch.object(test_handler.click, "confirm", side_effect=AssertionError("unexpected prompt")) as confirm,
    ):
        result = runner.invoke(cli_main.guard_main, ["test"])

    assert result.exit_code == 0
    run.assert_called_once()
    confirm.assert_not_called()
    assert all(not mock.called for mock in vars(guard_preconsent_sentinels).values())


def test_guard_non_test_command_preserves_normal_initialization(runner):
    keychain_value = object()
    chariot_value = object()
    with (
        patch.object(cli_main, "Keychain", return_value=keychain_value) as keychain,
        patch("praetorian_cli.sdk.chariot.Chariot", return_value=chariot_value) as chariot,
        patch.object(script_handler, "load_dynamic_commands") as loader,
    ):
        result = runner.invoke(cli_main.guard_main, ["list", "--help"])

    assert result.exit_code == 0
    keychain.assert_called_once_with("United States", None)
    chariot.assert_called_once_with(keychain_value, proxy="")
    loader.assert_called_once_with()


def test_legacy_non_test_command_preserves_normal_initialization(runner):
    keychain_value = object()
    chariot_value = object()
    with (
        patch.object(cli_main, "Keychain", return_value=keychain_value) as keychain,
        patch("praetorian_cli.sdk.chariot.Chariot", return_value=chariot_value) as chariot,
        patch.object(script_handler, "load_dynamic_commands") as loader,
    ):
        result = runner.invoke(cli_main.main, ["chariot", "list", "--help"])

    assert result.exit_code == 0
    keychain.assert_called_once_with("United States", None)
    chariot.assert_called_once_with(keychain=keychain_value, proxy="")
    loader.assert_called_once_with()


def test_live_confirmation_discloses_target_and_mutation(runner):
    result, run = _invoke(runner, ["--suite", "coherence"], input="y\n")

    assert result.exit_code == 0
    assert "coherence" in result.output
    assert PROFILE in result.output
    assert ACCOUNT in result.output
    assert "mutating" in result.output.lower()
    assert result.output.count("[y/N]") == 1
    run.assert_called_once()


def test_live_suite_propagates_exact_disclosed_target(runner):
    result, run = _invoke(runner, ["--suite", "coherence"], input="y\n")

    assert result.exit_code == 0
    environment = run.call_args.kwargs["env"]
    assert environment["CHARIOT_TEST_PROFILE"] == PROFILE
    assert environment["CHARIOT_TEST_ACCOUNT"] == ACCOUNT
    assert environment["CHARIOT_PROXY"] == "http://localhost:8080"


@pytest.mark.parametrize(("profile", "account"), [(PROFILE, None), (None, ACCOUNT), ("", ACCOUNT), (PROFILE, "")])
def test_missing_target_fails_before_subprocess(runner, profile, account):
    result, run = _invoke(
        runner,
        ["--suite", "coherence"],
        chariot=_chariot(profile=profile, account=account),
        input="y\n",
    )

    assert result.exit_code != 0
    run.assert_not_called()


def test_live_refusal_is_a_nonzero_noop(runner):
    result, run = _invoke(runner, ["--suite", "coherence"], input="n\n")

    assert result.exit_code != 0
    run.assert_not_called()


def test_live_confirmation_eof_is_a_nonzero_noop(runner):
    result, run = _invoke(runner, ["--suite", "coherence"], input="")

    assert result.exit_code != 0
    run.assert_not_called()


def test_safe_suite_is_noninteractive_and_keyless(runner):
    with patch.object(test_handler.click, "confirm", side_effect=AssertionError("unexpected prompt")) as confirm:
        result, run = _invoke(runner, [])

    assert result.exit_code == 0
    confirm.assert_not_called()
    command = run.call_args.args[0]
    assert command[-2:] == ["-m", "not coherence and not cli and not tui"]
    environment = run.call_args.kwargs["env"]
    assert "CHARIOT_TEST_PROFILE" not in environment
    assert "CHARIOT_TEST_ACCOUNT" not in environment


@pytest.mark.parametrize("suite", ["safe", "tui"])
def test_non_live_suite_scrubs_inherited_credentials(runner, suite):
    inherited = {name: f"sentinel-{index}" for index, name in enumerate(CREDENTIAL_ENV)}

    result, run = _invoke(runner, ["--suite", suite], env=inherited)

    assert result.exit_code == 0
    environment = run.call_args.kwargs["env"]
    assert all(
        name not in environment
        for name in CREDENTIAL_ENV
        if name not in CREDENTIAL_FILE_ENV
    )
    assert all(environment.get(name) != inherited[name] for name in CREDENTIAL_FILE_ENV)
    assert environment["AWS_EC2_METADATA_DISABLED"] == "true"


@pytest.mark.parametrize("suite", ["safe", "tui"])
def test_non_live_suite_isolates_default_credential_stores(runner, tmp_path, suite):
    ambient_home = tmp_path / "ambient-home"
    sentinel_paths = (
        ambient_home / ".praetorian" / "keychain.ini",
        ambient_home / ".aws" / "credentials",
        ambient_home / ".aws" / "config",
    )
    for path in sentinel_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("credential-sentinel", encoding="utf-8")

    observed = {}

    def inspect_environment(_args, *, env):
        isolated_home = Path(env["HOME"])
        observed.update(
            isolated_home=isolated_home,
            home_was_dir=isolated_home.is_dir(),
            userprofile=env.get("USERPROFILE"),
            shared_credentials_file=env.get("AWS_SHARED_CREDENTIALS_FILE"),
            aws_config_file=env.get("AWS_CONFIG_FILE"),
            boto_config=env.get("BOTO_CONFIG"),
            keychain_exists=(isolated_home / ".praetorian" / "keychain.ini").exists(),
        )
        return SimpleNamespace(returncode=0)

    with patch.object(test_handler.subprocess, "run", side_effect=inspect_environment) as run:
        result = runner.invoke(
            test_handler.test,
            ["--suite", suite],
            obj=_chariot(),
            env={"HOME": str(ambient_home), "USERPROFILE": str(ambient_home)},
        )

    assert result.exit_code == 0
    run.assert_called_once()
    isolated_home = observed["isolated_home"]
    assert observed["home_was_dir"]
    assert isolated_home != ambient_home
    assert observed["userprofile"] == str(isolated_home)
    assert observed["shared_credentials_file"] == str(isolated_home / ".aws" / "credentials")
    assert observed["aws_config_file"] == str(isolated_home / ".aws" / "config")
    assert observed["boto_config"] == str(isolated_home / ".boto")
    assert observed["keychain_exists"] is False


def test_live_suite_retains_inherited_auth_environment(runner):
    inherited = {name: f"sentinel-{index}" for index, name in enumerate(CREDENTIAL_ENV)}

    result, run = _invoke(runner, ["--suite", "coherence"], input="y\n", env=inherited)

    assert result.exit_code == 0
    environment = run.call_args.kwargs["env"]
    assert all(environment[name] == value for name, value in inherited.items())
    assert environment["CHARIOT_TEST_PROFILE"] == PROFILE
    assert environment["CHARIOT_TEST_ACCOUNT"] == ACCOUNT


@pytest.mark.parametrize(
    ("suite", "selector", "input"),
    [
        ("safe", "not coherence and not cli and not tui", None),
        ("coherence", "coherence", "y\n"),
        ("cli", "cli", "y\n"),
        ("tui", "tui", None),
    ],
)
def test_every_suite_uses_its_explicit_selector(runner, suite, selector, input):
    result, run = _invoke(runner, ["--suite", suite], input=input)

    assert result.exit_code == 0
    command = run.call_args.args[0]
    marker_index = max(index for index, argument in enumerate(command) if argument == "-m")
    assert command[marker_index + 1] == selector


def test_pytest_exit_status_is_propagated(runner):
    result, run = _invoke(runner, ["--suite", "coherence"], input="y\n", returncode=5)

    assert result.exit_code == 5
    run.assert_called_once()
