import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import click

import praetorian_cli.sdk.test as test_module
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@dataclass(frozen=True)
class TestSuite:
    name: str
    pytest_selector: tuple[str, ...]
    local_safe: bool
    live: bool
    mutating: bool
    tui: bool
    requires_target: bool


@dataclass(frozen=True)
class TestTarget:
    profile: str | None
    account: str | None
    proxy: str


TEST_SUITES = {
    "safe": TestSuite(
        name="safe",
        pytest_selector=("-m", "not coherence and not cli and not tui"),
        local_safe=True,
        live=False,
        mutating=False,
        tui=False,
        requires_target=False,
    ),
    "coherence": TestSuite(
        name="coherence",
        pytest_selector=("-m", "coherence"),
        local_safe=False,
        live=True,
        mutating=True,
        tui=False,
        requires_target=True,
    ),
    "cli": TestSuite(
        name="cli",
        pytest_selector=("-m", "cli"),
        local_safe=False,
        live=True,
        mutating=True,
        tui=False,
        requires_target=True,
    ),
    "tui": TestSuite(
        name="tui",
        pytest_selector=("-m", "tui"),
        local_safe=False,
        live=False,
        mutating=False,
        tui=True,
        requires_target=False,
    ),
}

TEST_PROFILE_ENV = "CHARIOT_TEST_PROFILE"
TEST_ACCOUNT_ENV = "CHARIOT_TEST_ACCOUNT"
TEST_PROXY_ENV = "CHARIOT_PROXY"
NON_LIVE_CREDENTIAL_ENV = (
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


def _explicit_target(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        click.echo(f"Error: an explicit, unambiguous {label} is required for this test suite.", err=True)
        raise SystemExit(2)
    return value


def _confirm_live_suite(suite, profile, account):
    prompt = (
        f"Suite: {suite.name}\n"
        f"Profile: {profile}\n"
        f"Account: {account}\n"
        f"Mutation status: {'MUTATING' if suite.mutating else 'non-mutating'}\n"
        f"Live status: {'LIVE' if suite.live else 'local'}\n"
        "Run this suite"
    )
    try:
        confirmed = click.confirm(prompt, default=False)
    except click.Abort:
        raise SystemExit(1)
    if not confirmed:
        raise SystemExit(1)


def _test_environment(suite):
    environment = os.environ.copy()
    for name in (TEST_PROFILE_ENV, TEST_ACCOUNT_ENV, TEST_PROXY_ENV):
        environment.pop(name, None)
    if not suite.live and not suite.mutating:
        for name in NON_LIVE_CREDENTIAL_ENV:
            environment.pop(name, None)
        environment["AWS_EC2_METADATA_DISABLED"] = "true"
    return environment


def _test_target(chariot):
    if isinstance(chariot, TestTarget):
        return chariot
    return TestTarget(
        profile=chariot.keychain.profile,
        account=chariot.keychain.account,
        proxy=chariot.proxy,
    )


def _configure_live_target(suite, target, environment):
    if not (suite.requires_target or suite.live or suite.mutating):
        return
    profile = _explicit_target(target.profile, 'profile')
    account = _explicit_target(target.account, 'account')
    environment[TEST_PROFILE_ENV] = profile
    environment[TEST_ACCOUNT_ENV] = account
    if target.proxy:
        environment[TEST_PROXY_ENV] = target.proxy
    if suite.live or suite.mutating:
        _confirm_live_suite(suite, profile, account)


def _pytest_args(suite, key):
    command = [test_module.__path__[0], *suite.pytest_selector]
    if key:
        command.extend(['-k', key])
    return [sys.executable, '-m', 'pytest', *command]


def _run_pytest(args, environment, *, isolated):
    if not isolated:
        return subprocess.run(args, env=environment)
    with tempfile.TemporaryDirectory(prefix="praetorian-cli-test-home-") as isolated_home:
        environment["HOME"] = isolated_home
        environment["USERPROFILE"] = isolated_home
        environment["AWS_SHARED_CREDENTIALS_FILE"] = os.path.join(isolated_home, ".aws", "credentials")
        environment["AWS_CONFIG_FILE"] = os.path.join(isolated_home, ".aws", "config")
        environment["BOTO_CONFIG"] = os.path.join(isolated_home, ".boto")
        return subprocess.run(args, env=environment)


@chariot.command()
@cli_handler
@click.option(
    '-s',
    '--suite',
    type=click.Choice(tuple(TEST_SUITES)),
    default='safe',
    show_default=True,
    help='Run a specific test suite',
)
@click.argument('key', required=False)
def test(chariot, key, suite):
    """ Run integration test suite """
    selected_suite = TEST_SUITES[suite]
    non_live = not selected_suite.live and not selected_suite.mutating
    environment = _test_environment(selected_suite)
    _configure_live_target(selected_suite, _test_target(chariot), environment)
    result = _run_pytest(_pytest_args(selected_suite, key), environment, isolated=non_live)
    raise SystemExit(result.returncode)
