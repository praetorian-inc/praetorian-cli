"""The SDK's raising contract: the library raises, only the CLI exits.

`praetorian_cli/sdk/**` used to report failures by calling
`praetorian_cli.handlers.utils.error()`, whose body is `click.secho(...)` +
`exit(1)`. That made library code do two things a library must not do:

* **terminate the host process.** `exit(1)` raises `SystemExit`, a
  `BaseException` -- so it is invisible to every `except Exception` an embedder
  writes. Measured: the `except Exception` in `praetorian_cli/sdk/mcp_server.py`
  and all 95 of them under `praetorian_cli/ui/` were bypassed, and a bad
  keychain killed the MCP server process outright.
* **depend on the presentation layer.** `praetorian_cli/sdk/*` imported
  `praetorian_cli/handlers/*`, inverting the intended one-way dependency.

These tests pin the replacement: the eight remaining exiting call sites raise
`praetorian_cli.sdk.exceptions` types, and the `@cli_handler` boundary
(`praetorian_cli/handlers/cli_decorators.py`) is the only thing that exits.

Scope note: this file's subject is the SDK's *raising* contract. The decorator
boundary's own contract is pinned separately in `test_cli_errors.py`, which
stays untouched -- `handlers.utils.error()` remains the handlers layer's helper
and has seven in-file callers plus every handler module.

Offline only: the child-process tests arm `requests.get` to `os._exit(97)`, so a
stray network call fails the return-code assertion instead of going out.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import praetorian_cli
import praetorian_cli.sdk
import praetorian_cli.sdk.keychain as keychain_module

# Imported, never transcribed -- same reason as test_cli_errors.py: these tests
# pin that the hint is *appended*, not what its wording is.
from praetorian_cli.handlers.cli_decorators import DEBUG_HINT
from praetorian_cli.sdk.entities.preseeds import Preseeds
from praetorian_cli.sdk.entities.seeds import Seeds
from praetorian_cli.sdk.exceptions import (
    AuthenticationError,
    ConfigurationError,
    GuardError,
    NotFoundError,
)
from praetorian_cli.sdk.keychain import Keychain

REPO_ROOT = Path(praetorian_cli.__file__).resolve().parent.parent
SDK_ROOT = Path(praetorian_cli.sdk.__file__).resolve().parent

TRACEBACK_HEADER = "Traceback (most recent call last)"

# A profile name no keychain file will ever hold, so the "profile not found"
# site is the one reached -- never a real profile of whoever runs the suite.
MISSING_PROFILE = "__no_such_profile__"

MISSING_SEED_KEY = "#asset#no-such-seed.example.com#no-such-seed.example.com"
MISSING_PRESEED_KEY = "#preseed#whois+company#No Such Company#no such company"

# A keychain whose single profile is complete, so `load()` reaches whichever
# later site a test is aiming at instead of failing early.
VALID_KEYCHAIN = """[United States]
api = https://api.invalid
client_id = test-client-id
"""

# Same, plus API-key credentials, so `has_api_key()` is genuinely true and
# `token()` takes the API-key branch rather than the Cognito one.
API_KEY_KEYCHAIN = """[United States]
api = https://api.invalid
client_id = test-client-id
api_key_id = test-key-id
api_key_secret = test-key-secret
"""

REJECTION_BODY = '{"message":"api key revoked"}'

SDK_ERROR_CLASSES = (GuardError, ConfigurationError, AuthenticationError, NotFoundError)


@pytest.fixture(autouse=True)
def _no_keychain_env_overrides(monkeypatch):
    """Strip `PRAETORIAN_*` from the environment for every test in this module.

    `Keychain.load_env` lets an environment variable override the keychain file,
    so a developer with `PRAETORIAN_CLI_API` exported would silently satisfy the
    "incomplete profile" site and turn that test green for the wrong reason.
    """
    for name in list(os.environ):
        if name.startswith("PRAETORIAN_"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def isolated_home(tmp_path):
    """A `$HOME` holding a controlled keychain, for the child-process CLI tests.

    `DEFAULT_KEYCHAIN_FILEPATH` is `join(Path.home(), '.praetorian',
    'keychain.ini')` resolved at import time, so a child process with `HOME`
    redirected here reads this file -- and one without it reads the developer's
    real keychain. The file has to *exist* and be valid, too: with no keychain at
    all `load()` falls back to built-in defaults and a bogus `--profile` would
    hit the "corrupted file" site instead of the "profile not found" one, making
    the assertion depend on whose machine ran it.
    """
    home = tmp_path / "home"
    (home / ".praetorian").mkdir(parents=True)
    (home / ".praetorian" / "keychain.ini").write_text(VALID_KEYCHAIN)
    return home


# Guard against the measurement trap that this repo makes easy: a second,
# pip-installed `praetorian_cli` is importable, and which one a child gets
# depends on how it was launched (`-c` prepends the cwd; a script file prepends
# the script's directory). Measured: launching the same probe as a file in a
# scratch directory imported a stale third checkout instead of this worktree.
# The child asserts its own package path and exits 98 rather than reporting a
# plausible number about code nobody is editing.
_PACKAGE_GUARD = """
import os, sys
import praetorian_cli
if not praetorian_cli.__file__.startswith(os.environ["PRAETORIAN_TEST_PACKAGE_ROOT"]):
    sys.stderr.write("imported the wrong praetorian_cli: %s\\n" % praetorian_cli.__file__)
    os._exit(98)
"""

# `upgrade_check`'s bare `except:` swallows anything raisable, so only an
# uncatchable exit makes a stray advisory request visible. Same device as
# `test_cli_errors.py`'s `_NETWORK_TRIPWIRE`, kept local so this module stands
# alone.
_CLI_NETWORK_TRIPWIRE = """
import os
import praetorian_cli.handlers.cli_decorators as decorators
decorators.requests.get = lambda *a, **k: os._exit(97)
"""

# The SDK-only counterpart, for the plain-script test: that script must not
# import the handlers layer at all, since not needing it is half the point.
# `Keychain.token()` is the only network call in `keychain.py`.
_SDK_NETWORK_TRIPWIRE = """
import os
import praetorian_cli.sdk.keychain as _keychain
_keychain.requests.get = lambda *a, **k: os._exit(97)
"""


def _run_child(script, tripwire, env=None):
    child_env = {k: v for k, v in os.environ.items() if not k.startswith("PRAETORIAN_")}
    child_env["PRAETORIAN_TEST_PACKAGE_ROOT"] = str(REPO_ROOT)
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", _PACKAGE_GUARD + tripwire + script],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
        env=child_env,
    )


# ---------------------------------------------------------------------------
# The hierarchy itself
# ---------------------------------------------------------------------------


def test_every_sdk_error_is_a_guard_error():
    """`except GuardError` is the blanket arm an embedder gets to rely on.

    Without this, the three concrete classes could each derive straight from
    `Exception` -- every message and per-site test below would still pass, and
    the one promise the base class exists to make would be silently broken.
    """
    for cls in (ConfigurationError, AuthenticationError, NotFoundError):
        assert cls is not GuardError
        assert issubclass(cls, GuardError), f"{cls.__name__} must subclass GuardError"

        caught = None
        try:
            raise cls("boom")
        except GuardError as exc:
            caught = exc
        assert isinstance(caught, cls)


def test_sdk_errors_are_not_base_exceptions():
    """This is the bug being fixed, stated as an assertion.

    Measured on the old code: `error('boom')` was catchable *only* as
    `SystemExit`, because `exit(1)` raises a `BaseException`. A class that
    accidentally derived from `SystemExit` would reintroduce exactly that,
    while every message-text test in this file still passed.
    """
    for cls in SDK_ERROR_CLASSES:
        assert issubclass(cls, Exception), f"{cls.__name__} must be an Exception"
        assert not issubclass(cls, SystemExit), f"{cls.__name__} must not exit the host"

        caught = None
        try:
            raise cls("boom")
        except Exception as exc:  # noqa: BLE001 - the blanket arm IS the contract
            caught = exc
        assert isinstance(caught, cls)
        assert str(caught) == "boom"


# ---------------------------------------------------------------------------
# The eight converted call sites
# ---------------------------------------------------------------------------


def test_corrupted_keychain_file_raises_configuration_error(tmp_path):
    """keychain.py `load()` -- no parseable profile sections at all."""
    path = tmp_path / "keychain.ini"
    # Comments only: a file that parses cleanly to *zero* sections. Arbitrary
    # bytes would not reach this site -- ConfigParser raises
    # MissingSectionHeaderError first, which is a different failure.
    path.write_text("# a keychain file with no profile sections\n")

    with pytest.raises(ConfigurationError) as raised:
        Keychain(filepath=str(path)).load()

    assert "Keychain file is corrupted" in str(raised.value)
    assert str(path) in str(raised.value)


def test_failed_load_is_not_cached_so_a_repaired_keychain_is_reread(tmp_path):
    """keychain.py `load()` -- a raise must not poison the instance for good.

    This is the half of the raising contract that only exists *because* the host
    now survives. While these sites called `exit(1)` no process lived long
    enough to hold stale state; now one does, and `load()`'s early return has to
    key on a load that finished rather than on `self.config` being set. Measured:
    `bool(ConfigParser())` is `True` and `len()` is 1 -- the DEFAULT section
    always counts, even with `sections() == []` -- so the parser assigned before
    validation is already truthy when the raise happens.

    The sequence is the operator's: a long-lived SDK or MCP host hits a corrupt
    keychain, catches `ConfigurationError`, the operator repairs the file, and
    the next call has to see the repair. Measured on the unfixed code the second
    `load()` returned the stale sectionless parser and every `get_option` read
    `None` -- `ConfigParser.get`'s `fallback=` swallows the missing section as
    well as a missing option, so the host went on silently seeing an unconfigured
    profile, with no second error, until it was restarted.
    """
    path = tmp_path / "keychain.ini"
    path.write_text("# no profile sections\n")

    keychain = Keychain(filepath=str(path))

    with pytest.raises(ConfigurationError):
        keychain.load()

    # The operator fixes the file the message pointed them at, in place.
    path.write_text(VALID_KEYCHAIN)

    assert keychain.load() is keychain
    assert keychain.get_option("api") == "https://api.invalid"
    assert keychain.get_option("client_id") == "test-client-id"


def test_rejected_required_option_is_not_cached_so_a_repaired_keychain_is_reread(
    tmp_path, monkeypatch
):
    """keychain.py `load_env()` -- its raise must invalidate the cached load too.

    The message at this site tells the operator to run `praetorian configure` or
    export the variable, so the instance has to be able to *see* that repair.
    Measured on the unfixed code, against a keychain that loads cleanly but
    carries no `username`: `load()` succeeded and set the cached-load flag, the
    direct `load_env('username', ...)` raised `ConfigurationError` while the flag
    stayed `True`, and after the operator added the line the second `load()`
    returned early without rereading -- `get_option('username')` read `None`
    indefinitely, while a fresh instance read `'fixed@example.com'`.

    Not a regression from the cached-load flag: the pre-existing `if self.config:`
    guard returned early here for exactly the same reason. The flag only made a
    long-standing memoization gap visible, so this test pins the raise path that
    the earlier one does not cover -- `load_env`'s, reached only by a direct call.
    """
    path = tmp_path / "keychain.ini"
    # Valid, and deliberately without `username` -- that is what VALID_KEYCHAIN
    # is: `api` and `client_id` only.
    path.write_text(VALID_KEYCHAIN)

    keychain = Keychain(filepath=str(path))
    assert keychain.load() is keychain

    # Before the call, not after: the environment branch takes precedence over
    # the file and would satisfy the option without ever reaching the raise.
    monkeypatch.delenv("PRAETORIAN_CLI_USERNAME", raising=False)

    with pytest.raises(ConfigurationError):
        keychain.load_env("username", "PRAETORIAN_CLI_USERNAME")

    # The operator does what the message said, in the profile the load used.
    with path.open("a") as keychain_file:
        keychain_file.write("username = fixed@example.com\n")

    assert keychain.load() is keychain
    assert keychain.get_option("username") == "fixed@example.com"


def test_missing_profile_raises_configuration_error(tmp_path):
    """keychain.py `load()` -- the requested profile is not in the file."""
    path = tmp_path / "keychain.ini"
    path.write_text(VALID_KEYCHAIN)

    with pytest.raises(ConfigurationError) as raised:
        Keychain(profile=MISSING_PROFILE, filepath=str(path)).load()

    assert MISSING_PROFILE in str(raised.value)
    assert str(path) in str(raised.value)


def test_incomplete_profile_raises_configuration_error(tmp_path):
    """keychain.py `load()` -- profile exists but lacks `api`/`client_id`."""
    path = tmp_path / "keychain.ini"
    path.write_text("[United States]\nusername = someone@example.invalid\n")

    with pytest.raises(ConfigurationError) as raised:
        Keychain(filepath=str(path)).load()

    assert "corrupted or incomplete" in str(raised.value)


def test_required_env_option_missing_raises_configuration_error():
    """keychain.py `load_env()` -- required option in neither file nor env.

    Reached only through a direct call: all six `load_env` calls inside `load()`
    pass `required=False`, so this site is unreachable from the CLI. It is a
    public method whose `required` parameter defaults to `True`, so it is
    converted with the rest and exercised here rather than through the CLI.
    """
    keychain = Keychain(data=VALID_KEYCHAIN).load()

    with pytest.raises(ConfigurationError) as raised:
        keychain.load_env("username", "PRAETORIAN_CLI_USERNAME", required=True)

    assert "PRAETORIAN_CLI_USERNAME" in str(raised.value)


def test_rejected_api_key_raises_authentication_error(monkeypatch):
    """keychain.py `token()` -- the backend rejected the credentials.

    `AuthenticationError`, not `ConfigurationError`: the local configuration is
    fine and the server said no, so the caller's move is to rotate or retry,
    not to re-run `configure`.
    """
    keychain = Keychain(data=API_KEY_KEYCHAIN)
    monkeypatch.setattr(
        keychain_module.requests,
        "get",
        Mock(return_value=Mock(status_code=401, text=REJECTION_BODY)),
    )

    with pytest.raises(AuthenticationError) as raised:
        keychain.token()

    # The response body is the only actionable detail the caller gets; the
    # boundary surfaces the message verbatim, so it has to survive to here.
    assert REJECTION_BODY in str(raised.value)


def _seeds_finding_nothing():
    """A `Seeds` whose backing search returns no results, so `get()` is None."""
    api = Mock()
    api.search.by_query.return_value = None
    return Seeds(api)


def test_seeds_update_missing_key_raises_not_found_error():
    """seeds.py `update()` -- `NotFoundError` is ordinary control flow.

    A caller iterating keys wants `except NotFoundError: continue`, which the
    old `exit(1)` made impossible.
    """
    with pytest.raises(NotFoundError) as raised:
        _seeds_finding_nothing().update(MISSING_SEED_KEY, "A")

    assert MISSING_SEED_KEY in str(raised.value)


def test_seeds_delete_missing_key_raises_not_found_error():
    """seeds.py `delete()`."""
    with pytest.raises(NotFoundError) as raised:
        _seeds_finding_nothing().delete(MISSING_SEED_KEY)

    assert MISSING_SEED_KEY in str(raised.value)


def test_preseeds_update_missing_key_raises_not_found_error():
    """preseeds.py `update()`."""
    api = Mock()
    api.search.by_exact_key.return_value = None

    with pytest.raises(NotFoundError) as raised:
        Preseeds(api).update(MISSING_PRESEED_KEY, "A")

    assert MISSING_PRESEED_KEY in str(raised.value)


# ---------------------------------------------------------------------------
# An embedding host survives (the whole point of the change)
# ---------------------------------------------------------------------------


_PLAIN_SCRIPT_CATCHING_CONFIGURATION_ERROR = """
import sys
from praetorian_cli.sdk.exceptions import ConfigurationError
from praetorian_cli.sdk.keychain import Keychain

try:
    Keychain(profile={profile!r}, filepath={path!r}).load()
except ConfigurationError as exc:
    print("CAUGHT", type(exc).__name__)
    sys.exit(0)

print("NOT RAISED")
sys.exit(3)
"""


def test_plain_script_catches_configuration_error_and_survives(tmp_path):
    """A child process is load-bearing here, not ceremony.

    The claim is that the *host process survives*, and an in-process
    `pytest.raises` cannot show that: under the old code `exit(1)` raised
    `SystemExit`, so this script's `except ConfigurationError` never ran and the
    process died with status 1 and `ERROR:` on stderr. Only a real process can
    distinguish "caught and continued" from "was killed".
    """
    path = tmp_path / "keychain.ini"
    path.write_text(VALID_KEYCHAIN)

    result = _run_child(
        _PLAIN_SCRIPT_CATCHING_CONFIGURATION_ERROR.format(
            profile=MISSING_PROFILE, path=str(path)
        ),
        tripwire=_SDK_NETWORK_TRIPWIRE,
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "CAUGHT ConfigurationError" in result.stdout


# ---------------------------------------------------------------------------
# No user-facing regression at either console script
# ---------------------------------------------------------------------------


_CLI_SCRIPT = """
from praetorian_cli.main import {entry}
{entry}({argv!r})
"""


def _cli_child(entry, argv, home):
    return _run_child(
        _CLI_SCRIPT.format(entry=entry, argv=argv),
        tripwire=_CLI_NETWORK_TRIPWIRE,
        env={"HOME": str(home)},
    )


def _assert_handled_cli_failure(result):
    combined = result.stdout + result.stderr
    # `== 1`, never `!= 0`: an argument-parsing mistake exits 2 without ever
    # reading the keychain, and a stray network call exits 97 -- both would
    # satisfy a loose assertion while measuring nothing about this change.
    assert result.returncode == 1, f"exit={result.returncode} output={combined!r}"
    assert MISSING_PROFILE in result.stderr, combined
    assert DEBUG_HINT in result.stderr, combined
    assert TRACEBACK_HEADER not in combined, combined


def test_guard_entry_point_missing_profile_is_a_handled_failure(isolated_home):
    """`guard --profile ... list assets`: exit 1, own message, no traceback."""
    result = _cli_child(
        "guard_main", ["--profile", MISSING_PROFILE, "list", "assets"], isolated_home
    )
    _assert_handled_cli_failure(result)


def test_praetorian_entry_point_missing_profile_is_a_handled_failure(isolated_home):
    """`praetorian --profile ... chariot list assets`, same contract.

    The two console scripts carry *different* command sets (`praetorian` ->
    `main`, `guard` -> `guard_main`), so measuring one is not evidence about the
    other. The `chariot` segment is required: measured, dropping it exits 2 with
    `Error: No such command 'list'.` and never reaches the keychain.
    """
    result = _cli_child(
        "main",
        ["--profile", MISSING_PROFILE, "chariot", "list", "assets"],
        isolated_home,
    )
    _assert_handled_cli_failure(result)


# ---------------------------------------------------------------------------
# The dependency direction, as a test rather than a grep
# ---------------------------------------------------------------------------


# WHY THE TEST TREE IS EXCLUDED -- read this before "fixing" a red result here.
# The CLI's own tests deliberately live under the SDK's test tree and import the
# CLI layer *in order to test it*: `test_cli_errors.py` alone carries nine such
# imports. Measured on 556e63a: 18 matches under praetorian_cli/sdk/, 13 of them
# in this directory. So the rule being enforced is about SHIPPING SDK code.
# Reading it as "no such import anywhere under sdk/" would mean deleting working
# tests to quiet a grep -- do NOT resolve a failure here by touching
# praetorian_cli/sdk/test/.
SDK_TEST_TREE = SDK_ROOT / "test"

_HANDLERS_IMPORT = re.compile(r"\s*(?:from|import)\s+praetorian_cli\.handlers\b")


def test_sdk_does_not_import_the_handlers_layer():
    """A walk, not a hardcoded file list, so a *new* SDK module cannot slip one in."""
    offenders = []
    for module in sorted(SDK_ROOT.rglob("*.py")):
        if SDK_TEST_TREE in module.parents:
            continue
        for lineno, line in enumerate(module.read_text().splitlines(), start=1):
            if _HANDLERS_IMPORT.match(line):
                offenders.append(f"{module.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert offenders == [], (
        "SDK code must not import the CLI handlers layer:\n" + "\n".join(offenders)
    )
