"""Error-boundary contract for the shared `@cli_handler` decorator.

`handle_error` used to end every unexpected failure with `error(str(e), quit=False)`,
which printed and *returned* -- so the decorated command returned `None` normally and
the process exited 0 on every failure. These tests pin the replacement contract:

* an unexpected exception exits non-zero and keeps *its own* message, because the
  SDK raises bare `Exception`/`ValueError` as its normal error-reporting mechanism
  (`Chariot.process_failure` raises `Exception('[404] Request failed\\nError: ...')`,
  `assets.py` raises `ValueError('Invalid asset type: ...')`) -- replacing that text
  destroys the only actionable detail the user gets,
* *every* non-debug error message ends with `cli_decorators.DEBUG_HINT` on its own
  trailing line, exactly once, with the original message left intact ahead of it --
  so a user who gets only a one-line message still learns how to obtain the
  traceback. A message-less exception falls back to the exception's type name and
  carries the hint just the same,
* no raw traceback reaches the user unless `--debug` is passed,
* `--debug` gives the original exception (and its traceback, on stderr) back --
  unwrapped and hint-free, since the traceback the hint advertises is already there,
* and the deliberate control-flow exceptions -- `ClickException`, `Abort`,
  `Exit`, `CancelledError`, `SystemExit` -- keep their own status and text
  instead of being flattened into a generic failure.

Message *redaction* is deliberately out of scope here: it needs the SDK exception
hierarchy (ENG-6570) to classify what is safe to show, and is owned by ENG-6781.

Offline only. Most tests here raise before `upgrade_check` can reach the network
and arm `requests.get` to fail loudly if that ever stops being true; the final
group deliberately lets the advisory run, with `requests.get` replaced and
`XDG_CACHE_HOME` redirected at `tmp_path`, to pin that its failures cannot change
a command's outcome.
"""

import asyncio
import subprocess
import sys
import threading
from concurrent.futures import CancelledError as FutureCancelledError
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

# Imported, never transcribed: these tests pin that the hint is *appended*, not
# what its wording is. A copied literal would let the source's text drift away
# from the suite's silently -- and would turn a deliberate re-wording into a
# spurious test failure here.
from praetorian_cli.handlers.cli_decorators import DEBUG_HINT

# Imported for the same reason: the deadline test asserts the join was handed the
# module's own budget, so a re-tuned budget must not need a matching edit here.
from praetorian_cli.handlers.cli_decorators import UPDATE_CHECK_DEADLINE_SECONDS

# The exact shape `Chariot.process_failure` raises on a failed API call
# (praetorian_cli/sdk/chariot.py). Both halves -- the status line and the response
# body -- have to reach the user.
SDK_API_FAILURE_MESSAGE = '[404] Request failed\nError: {"message":"asset not found"}'

# The shape the SDK entity helpers raise on bad input, e.g.
# `raise ValueError(f'Invalid asset type: {asset_type}')` in
# praetorian_cli/sdk/entities/assets.py.
SDK_VALIDATION_MESSAGE = 'Invalid asset type: bogus'

TRACEBACK_HEADER = "Traceback (most recent call last)"


class SentinelBaseException(BaseException):
    pass


def _command_raising(exception):
    from praetorian_cli.handlers.cli_decorators import cli_handler

    @click.command()
    @cli_handler
    def command(_sdk):
        raise exception

    return command


def _command_calling(action):
    """A `@cli_handler` command whose body runs `action()` instead of raising.

    Needed for the paths a bare `raise` cannot express: `ctx.exit(...)`, which
    Click raises for you, and `utils.error(...)`, which exits from inside the
    handled-error helper.
    """
    from praetorian_cli.handlers.cli_decorators import cli_handler

    @click.command()
    @cli_handler
    def command(_sdk):
        return action()

    return command


def _debug_root(command):
    """A root group carrying the real `--debug` flag, with `command` mounted on it.

    `handle_error` reads the flag off the root context's params
    (`ctx.find_root().params["debug"]`), not off the `chariot` group -- so a
    synthetic root that declares `--debug` is a faithful stand-in. The real
    `guard_main` is deliberately NOT used: it builds a `Chariot(Keychain(...))`
    and is not offline-safe.
    """

    @click.group()
    @click.option("--debug", is_flag=True)
    @click.pass_context
    def root(ctx, debug):
        ctx.obj = object()

    root.add_command(command)
    return root


def _successful_command():
    """A `@cli_handler` command that succeeds, so `upgrade_check` actually runs."""
    from praetorian_cli.handlers.cli_decorators import cli_handler

    @click.command()
    @cli_handler
    def command(_sdk):
        return "done"

    return command


def _force_update_request(monkeypatch, tmp_path, side_effect):
    """The inverse of `_disable_update_request`: let the advisory reach the network.

    Two forces are needed and both are load-bearing. `_session_is_interactive()`
    requires BOTH `sys.stdout.isatty()` and `sys.stderr.isatty()`, and `CliRunner`
    replaces both with non-tty buffers, so the gate is closed inside any `invoke`
    and the advisory returns before it does anything -- a test that did not force
    it would assert against a check that never ran, and would keep passing if the
    advisory stopped running altogether. Forcing the whole predicate rather than
    one stream is what keeps that hole shut. `XDG_CACHE_HOME` is redirected at
    `tmp_path` so nothing reads or writes the real user cache, and an empty cache
    is what guarantees the network branch is the one taken.

    The predicate's own behaviour is pinned in test_update_check.py, which drives
    the real `_session_is_interactive` instead of replacing it.
    """
    import praetorian_cli.handlers.cli_decorators as decorators

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("PRAETORIAN_CLI_DISABLE_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(decorators, "_session_is_interactive", lambda: True)
    request = Mock(side_effect=side_effect)
    monkeypatch.setattr(decorators.requests, "get", request)
    return request


def _disable_update_request(monkeypatch):
    import praetorian_cli.handlers.cli_decorators as decorators

    request = Mock(side_effect=AssertionError("update check ran after failed command"))
    monkeypatch.setattr(decorators.requests, "get", request)
    return request


# `_check_for_update`'s `except Exception: pass` arm swallows every ordinary
# exception -- an in-process `AssertionError` included -- so an in-process guard
# cannot make a stray network call visible in a child process. `os._exit` cannot
# be caught: if the advisory ever runs, the child's status is 97 and the
# return-code assertion fails instead of the request silently going out.
_NETWORK_TRIPWIRE = """
import os
import praetorian_cli.handlers.cli_decorators as decorators
decorators.requests.get = lambda *a, **k: os._exit(97)
"""


def _run_child(script):
    return subprocess.run(
        [sys.executable, "-c", _NETWORK_TRIPWIRE + script],
        capture_output=True,
        text=True,
        check=False,
    )


def test_ordinary_exception_keeps_its_message_in_normal_mode_and_chained(monkeypatch):
    request = _disable_update_request(monkeypatch)
    cause = RuntimeError("UNEXPECTED_SENTINEL")

    result = CliRunner().invoke(
        _command_raising(cause),
        obj=object(),
        standalone_mode=False,
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, click.ClickException)
    assert result.exception.__cause__ is cause
    assert str(result.exception) == f"UNEXPECTED_SENTINEL\n{DEBUG_HINT}"
    request.assert_not_called()


# --- SDK-shaped failures: the messages the CLI exists to relay ------------------
#
# The SDK reports every API and validation failure by raising bare `Exception` /
# `ValueError` with the actionable text in the message. A handler that replaces
# that text with a generic string satisfies ENG-6641's exit-code AC while
# destroying the only thing the user can act on -- these tests catch that.


def test_sdk_api_failure_message_reaches_the_user(monkeypatch):
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(
        _command_raising(Exception(SDK_API_FAILURE_MESSAGE)),
        obj=object(),
    )

    assert result.exit_code == 1
    # `result.output` is the interleaved stdout+stderr stream; `result.stdout` is
    # empty on this path, so asserting against it would be vacuous.
    assert "[404] Request failed" in result.output
    assert "asset not found" in result.output
    assert TRACEBACK_HEADER not in result.output
    request.assert_not_called()


def test_sdk_validation_failure_message_reaches_the_user(monkeypatch):
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(
        _command_raising(ValueError(SDK_VALIDATION_MESSAGE)),
        obj=object(),
    )

    assert result.exit_code == 1
    assert SDK_VALIDATION_MESSAGE in result.output
    assert TRACEBACK_HEADER not in result.output
    request.assert_not_called()


def test_blank_message_falls_back_to_the_exception_type(monkeypatch):
    """A message-less exception must not render as a bare `Error:` with nothing after it."""
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_raising(Exception()), obj=object())

    assert result.exit_code == 1
    assert "Error: Exception" in result.output
    assert "--debug" in result.output
    assert TRACEBACK_HEADER not in result.output
    request.assert_not_called()


# --- the `--debug` hint: appended to EVERY non-debug message ---------------------
#
# The hint used to appear only when `str(exc)` was blank, which left the common
# case -- a real SDK message -- with no way for the user to discover `--debug`.
# It is now appended unconditionally, so the non-blank cases below are the newly
# introduced behaviour and the blank ones pin the half that was preserved.


@pytest.mark.parametrize(
    ("exception", "expected_body"),
    [
        (Exception(SDK_API_FAILURE_MESSAGE), SDK_API_FAILURE_MESSAGE),
        (ValueError(SDK_VALIDATION_MESSAGE), SDK_VALIDATION_MESSAGE),
        (Exception(SDK_API_FAILURE_MESSAGE + '\n'), SDK_API_FAILURE_MESSAGE),
        (Exception(), "Exception"),
        (ValueError("   "), "ValueError"),
    ],
    ids=[
        "multi-line-sdk-message",
        "single-line-sdk-message",
        "sdk-message-with-trailing-newline",
        "no-message",
        "whitespace-only-message",
    ],
)
def test_debug_hint_is_appended_once_after_the_intact_message(
    monkeypatch,
    exception,
    expected_body,
):
    """The hint is a trailing line appended to the message, exactly once.

    Exact equality is what makes this a contract rather than a smoke test: it pins
    that the body survives *verbatim and in full* ahead of the hint. A containment
    check would pass on a message the boundary had truncated, reordered, or spliced
    the hint into the middle of -- the multi-line SDK case is precisely where that
    could happen unnoticed.

    The `count` assertion is not redundant with it. Equality pins today's single
    occurrence; `count` names *double-appending* as the specific regression being
    guarded -- a second `@handle_error` in the decorator chain, or a hint added to
    both branches of a re-split `_error_message`, would append it twice.

    The two blank cases also pin the preserved fallback to the exception's type
    name (`.strip()` is what makes whitespace-only count as blank). The
    trailing-newline case is the other half of that same trim -- a real HTTP
    response body can end in one -- and pins that the hint still lands on the
    line *immediately* after the message, never after a blank one.
    """
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(
        _command_raising(exception),
        obj=object(),
        standalone_mode=False,
    )

    assert result.exit_code == 1
    assert str(result.exception) == f"{expected_body}\n{DEBUG_HINT}"
    assert str(result.exception).count(DEBUG_HINT) == 1
    request.assert_not_called()


def test_debug_mode_adds_no_hint_and_leaves_the_exception_unwrapped(monkeypatch):
    """`--debug` is unaffected: the original exception propagates, hint-free.

    The hint exists to tell a user how to reach a traceback. Under `--debug` they
    already have one, and `_error_message` is never reached -- so the hint must not
    appear anywhere in the traceback path, and the exception must arrive unwrapped
    rather than as a `ClickException` carrying an annotated message.

    Identity is measured in-process; the absence of the hint from the real output
    stream has to be measured in a child process, because `CliRunner` intercepts
    the re-raise before Python prints anything.
    """
    request = _disable_update_request(monkeypatch)
    cause = RuntimeError("DEBUG_NO_HINT_SENTINEL")
    command = _command_raising(cause)

    result = CliRunner().invoke(_debug_root(command), ["--debug", command.name])

    assert result.exit_code == 1
    assert result.exception is cause
    # Not re-wrapped, and no hint spliced into its message.
    assert str(result.exception) == "DEBUG_NO_HINT_SENTINEL"
    request.assert_not_called()

    child = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.group()
@click.option("--debug", is_flag=True)
@click.pass_context
def root(ctx, debug):
    ctx.obj = object()

@root.command()
@cli_handler
def command(_sdk):
    raise RuntimeError("DEBUG_NO_HINT_SENTINEL")

root.main(["--debug", "command"])
"""
    )

    output = child.stdout + child.stderr
    assert child.returncode == 1
    assert TRACEBACK_HEADER in child.stderr
    assert "DEBUG_NO_HINT_SENTINEL" in child.stderr
    assert DEBUG_HINT not in output


def test_debug_mode_preserves_sdk_error_identity_and_traceback(monkeypatch):
    """`--debug` on an SDK-shaped failure: same exception object, real traceback.

    Identity is measured in-process (`CliRunner` intercepts the re-raise), while
    the traceback has to be measured in a real child process -- `CliRunner`
    catches the exception before Python can print one.
    """
    request = _disable_update_request(monkeypatch)
    cause = Exception(SDK_API_FAILURE_MESSAGE)
    command = _command_raising(cause)

    result = CliRunner().invoke(_debug_root(command), ["--debug", command.name])

    assert result.exit_code == 1
    assert result.exception is cause
    request.assert_not_called()

    child = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.group()
@click.option("--debug", is_flag=True)
@click.pass_context
def root(ctx, debug):
    ctx.obj = object()

@root.command()
@cli_handler
def command(_sdk):
    raise Exception('[404] Request failed\\nError: {"message":"asset not found"}')

root.main(["--debug", "command"])
"""
    )

    assert child.returncode == 1
    assert TRACEBACK_HEADER in child.stderr
    assert "[404] Request failed" in child.stderr
    assert "asset not found" in child.stderr


@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_text"),
    [
        (click.ClickException("actionable failure"), 1, "actionable failure"),
        (click.UsageError("actionable usage guidance"), 2, "actionable usage guidance"),
    ],
)
def test_deliberate_click_exceptions_preserve_status_and_actionable_text(
    monkeypatch,
    exception,
    expected_status,
    expected_text,
):
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_raising(exception), obj=object())

    assert result.exit_code == expected_status
    assert expected_text in result.output
    assert TRACEBACK_HEADER not in result.output
    request.assert_not_called()


def test_explicit_debug_mode_preserves_unexpected_exception_identity(monkeypatch):
    request = _disable_update_request(monkeypatch)
    cause = RuntimeError("debug details")
    command = _command_raising(cause)

    result = CliRunner().invoke(_debug_root(command), ["--debug", command.name])

    assert result.exit_code == 1
    assert result.exception is cause
    assert result.exc_info is not None
    request.assert_not_called()


def test_real_process_normal_mode_shows_message_without_traceback():
    result = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.command()
@cli_handler
def command(_sdk):
    raise RuntimeError("UNEXPECTED_SENTINEL")

command.main(obj=object())
"""
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    # Whole rendered stream, exactly: Click's `Error: ` prefix, the message, then
    # the hint on its own line. Nothing else -- no traceback, no update advisory.
    assert output == f"Error: UNEXPECTED_SENTINEL\n{DEBUG_HINT}\n"
    assert "Traceback" not in output


def test_real_process_debug_mode_preserves_unexpected_traceback_and_message():
    result = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.group()
@click.option("--debug", is_flag=True)
@click.pass_context
def root(ctx, debug):
    ctx.obj = object()

@root.command()
@cli_handler
def command(_sdk):
    raise RuntimeError("DEBUG_UNEXPECTED_SENTINEL")

root.main(["--debug", "command"])
"""
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "DEBUG_UNEXPECTED_SENTINEL" in output
    assert "Traceback" in output


def test_debug_traceback_goes_to_stderr_not_stdout():
    """A caller piping stdout must not receive a traceback in its data stream.

    The old implementation printed it with `click.echo(traceback.format_exc())`
    -- no `err=True` -- so `guard --debug ... > data.json` interleaved a
    traceback into the file. Measured in a real child process rather than with
    `CliRunner`: `CliRunner`'s `catch_exceptions=True` intercepts the re-raised
    exception before any traceback is printed, so it cannot observe the stream
    the traceback lands on at all.
    """
    result = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.group()
@click.option("--debug", is_flag=True)
@click.pass_context
def root(ctx, debug):
    ctx.obj = object()

@root.command()
@cli_handler
def command(_sdk):
    raise RuntimeError("STREAM_SENTINEL")

root.main(["--debug", "command"])
"""
    )

    assert result.returncode == 1
    assert "Traceback" in result.stderr
    assert "STREAM_SENTINEL" in result.stderr
    assert result.stdout == ""


def test_keyboard_interrupt_keeps_click_abort_semantics_and_skips_update(monkeypatch):
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_raising(KeyboardInterrupt()), obj=object())

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert "Error:" not in result.output
    request.assert_not_called()


@pytest.mark.parametrize("exception", [asyncio.CancelledError(), SentinelBaseException("stop")])
def test_cancellation_and_base_exception_are_not_translated_or_swallowed(monkeypatch, exception):
    request = _disable_update_request(monkeypatch)

    with pytest.raises(type(exception)) as raised:
        CliRunner().invoke(_command_raising(exception), obj=object())

    assert raised.value is exception
    request.assert_not_called()


def test_future_cancellation_is_not_translated_or_swallowed(monkeypatch):
    """`concurrent.futures.CancelledError` derives from `Exception` on this runtime.

    Unlike `asyncio.CancelledError` (a `BaseException` since 3.8) the futures
    variant is caught by a bare `except Exception`, so the dedicated arm is what
    keeps a cancelled background task from being reported as an unexpected bug.
    """
    request = _disable_update_request(monkeypatch)
    exception = FutureCancelledError("cancelled")

    assert issubclass(FutureCancelledError, Exception)
    assert FutureCancelledError is not asyncio.CancelledError

    result = CliRunner().invoke(_command_raising(exception), obj=object())

    assert result.exit_code == 1
    assert result.exception is exception
    request.assert_not_called()


def test_abort_keeps_its_own_message_and_exit_code(monkeypatch):
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_raising(click.Abort()), obj=object())

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert "Error:" not in result.output
    request.assert_not_called()


def test_ctx_exit_zero_stays_a_success(monkeypatch):
    """`ctx.exit(0)` must remain a success.

    `click.exceptions.Exit` is a `RuntimeError`, so without its own arm a
    deliberate early success is caught by the generic handler and reported as a
    failure -- turning `exit 0` into `exit 1`.
    """
    request = _disable_update_request(monkeypatch)
    command = _command_calling(lambda: click.get_current_context().exit(0))

    result = CliRunner().invoke(command, obj=object())

    assert result.exit_code == 0
    assert result.output == ""
    assert result.exception is None
    request.assert_not_called()


def test_ctx_exit_nonzero_preserves_its_status(monkeypatch):
    request = _disable_update_request(monkeypatch)
    command = _command_calling(lambda: click.get_current_context().exit(3))

    result = CliRunner().invoke(command, obj=object())

    assert result.exit_code == 3
    assert result.output == ""
    request.assert_not_called()


def test_sys_exit_passes_through_unchanged(monkeypatch):
    """`SystemExit` is a `BaseException`; the chain must not start catching it."""
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_calling(lambda: sys.exit(7)), obj=object())

    assert result.exit_code == 7
    assert "Error:" not in result.output
    request.assert_not_called()


def test_handled_user_facing_error_is_unchanged(monkeypatch):
    """The *handled* error path is untouched by this change.

    `utils.error` prints `ERROR: <message>` to stderr and exits 1. It must keep
    its own actionable text and must not be re-labelled with Click's `Error:`
    prefix.
    """
    from praetorian_cli.handlers.utils import error

    request = _disable_update_request(monkeypatch)
    command = _command_calling(lambda: error("profile 'staging' is not configured"))

    result = CliRunner().invoke(command, obj=object())

    assert result.exit_code == 1
    assert "ERROR: profile 'staging' is not configured" in result.stderr
    assert "Error:" not in result.output
    request.assert_not_called()


# --- the update advisory on a SUCCESSFUL command --------------------------------
#
# The cases above all raise, so `upgrade_check` never reaches `_check_for_update`.
# These pin the other half: when the command succeeds the advisory does run, and
# its own failures must not be able to change the outcome the user already earned.
#
# That holds for a Ctrl-C too, which is the correction ENG-6643 makes: the
# advisory is a trailing informational courtesy, so an interrupt arriving during
# it cannot retroactively fail work the user has already been handed. Process
# control that the *process itself* initiated -- `sys.exit()`, a cancelled task --
# is the deliberate exception and still reaches the exit status.


def test_ordinary_update_advisory_failure_remains_fail_open(monkeypatch, tmp_path):
    """An ordinary advisory failure is swallowed; the command still succeeds."""
    request = _force_update_request(monkeypatch, tmp_path, RuntimeError("advisory unavailable"))

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == 0
    assert result.exception is None
    assert "advisory unavailable" not in result.output
    request.assert_called_once()


def _interrupt_the_deadline_wait(monkeypatch, exception):
    """Raise `exception` in the main thread, where a real Ctrl-C would surface.

    The advisory's fetch runs on a worker thread and the main thread waits it out
    in `Thread.join(UPDATE_CHECK_DEADLINE_SECONDS)`, so that join -- not
    `requests.get` -- is where an interrupt during the advisory actually lands:
    CPython delivers SIGINT to the main thread only, and a worker parked in a
    socket read never receives it. Injecting at `requests.get` instead would put
    the exception inside the worker, whose `except BaseException: pass` discards
    it, and the test would pass for the wrong reason.

    The real `join` runs FIRST, before the exception is raised, so the worker has
    already finished and its `requests.get` call is recorded by the time control
    returns -- otherwise the call assertion would race the worker.

    `threading` is referenced exactly once in the module under test (that join),
    so shimming the module attribute reaches that one call and nothing else.
    Returns the list of timeouts the shim observed, so a test can prove the seam
    fired rather than passing because it was never reached.
    """
    import praetorian_cli.handlers.cli_decorators as decorators

    joined_with = []

    class _InterruptedJoin(threading.Thread):
        def join(self, timeout=None):
            super().join(timeout)
            joined_with.append(timeout)
            raise exception

    class _ThreadingShim:
        Thread = _InterruptedJoin

    monkeypatch.setattr(decorators, "threading", _ThreadingShim)
    return joined_with


def test_update_keyboard_interrupt_leaves_the_finished_command_successful(monkeypatch, tmp_path):
    """A Ctrl-C during the trailing advisory must not fail a command that already succeeded.

    This is the corrected contract (ENG-6643, finding R4-3). The command's own
    work is complete and its output already delivered before `upgrade_check`
    calls the advisory; letting a `KeyboardInterrupt` from that trailing courtesy
    become `Aborted!` and exit 1 tells the user their command failed when it did
    not -- and invites whoever wrote `guard list assets && next-step` to re-run
    work that already succeeded. Measured on the real CLI before the fix: 968
    asset rows and the pagination hint were printed, the process then sat alive
    10.1s past its own output, and Ctrl-C there produced `Aborted!` and exit 1.

    `upgrade_check`'s `except KeyboardInterrupt: pass` is what closes that, and it
    is deliberately narrow: it wraps only the advisory call, so a Ctrl-C during
    the command's own body still aborts (pinned by
    `test_keyboard_interrupt_keeps_click_abort_semantics_and_skips_update`), and
    it names `KeyboardInterrupt` alone, so `SystemExit` and cancellation still
    propagate (pinned directly below).

    The interrupt is injected at the deadline wait rather than at `requests.get`
    -- see `_interrupt_the_deadline_wait` for why that is the only reachable
    seam. `joined_with` is asserted first because every other assertion here
    would also hold if the shim were never installed; without it a green run
    would prove nothing.
    """
    request = _force_update_request(monkeypatch, tmp_path, TimeoutError("fetch still in flight"))
    joined_with = _interrupt_the_deadline_wait(monkeypatch, KeyboardInterrupt())
    command = _command_calling(lambda: click.echo("delivered-before-the-interrupt"))

    result = CliRunner().invoke(command, obj=object())

    assert joined_with == [UPDATE_CHECK_DEADLINE_SECONDS]
    assert result.exit_code == 0
    assert result.exception is None
    assert "Aborted!" not in result.output
    assert "Error:" not in result.output
    assert result.output == "delivered-before-the-interrupt\n"
    request.assert_called_once()


def _raise_from_the_throttle_write(monkeypatch, exception):
    """Raise `exception` from the throttle-record write, on the main thread.

    `_check_for_update` writes the throttle record *before* it goes anywhere near
    the network, so this is the earliest main-thread step of the advisory that can
    fail -- and it is reached through the real `_write_update_check_cache`, so that
    function's own arms (`except CancelledError: raise`, then
    `except Exception: return False`) are exercised rather than replaced.

    It also makes the fetch provably unreached, which is what the
    `request.assert_not_called()` in the caller records.
    """
    import praetorian_cli.handlers.cli_decorators as decorators

    def raise_during_the_write(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(decorators.json, "dump", raise_during_the_write)


@pytest.mark.parametrize(
    ("exception", "exit_code"),
    [(SystemExit(73), 73), (FutureCancelledError("cancelled"), 1)],
    ids=["system-exit", "future-cancelled"],
)
def test_update_process_control_exceptions_propagate(monkeypatch, tmp_path, exception, exit_code):
    """Process control raised by the advisory still reaches the exit status.

    `KeyboardInterrupt` is now absorbed (above); these two are not, and the
    distinction is the point. A `SystemExit` means something in the process asked
    to exit with that status, and a `CancelledError` means the surrounding task
    was cancelled -- neither is "the user interrupted a courtesy message", so
    neither may be reported as a clean success. `SystemExit` is a `BaseException`
    and passes through `except Exception` untouched, keeping its own status;
    `concurrent.futures.CancelledError` is `Exception`-derived on this runtime, so
    the fail-open arm *would* swallow it and the dedicated
    `except CancelledError: raise` arm is what makes it propagate instead.

    Anchored at the throttle write, a main-thread step, rather than at
    `requests.get`: the fetch now runs on a worker thread whose body is
    `except BaseException: pass`, so nothing raised there reaches the main thread
    at all. `request.assert_not_called()` is the negative half of that -- control
    never got as far as the network.
    """
    assert issubclass(FutureCancelledError, Exception)
    request = _force_update_request(monkeypatch, tmp_path, AssertionError("must not be reached"))
    _raise_from_the_throttle_write(monkeypatch, exception)

    result = CliRunner().invoke(_successful_command(), obj=object())

    assert result.exit_code == exit_code
    assert result.exception is exception
    request.assert_not_called()
