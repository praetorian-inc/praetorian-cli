"""Error-boundary contract for the shared `@cli_handler` decorator.

`handle_error` used to end every unexpected failure with `error(str(e), quit=False)`,
which printed and *returned* -- so the decorated command returned `None` normally and
the process exited 0 on every failure. These tests pin the replacement contract:

* an unexpected exception exits non-zero with a redacted, actionable message,
* `--debug` gives the original exception (and its traceback, on stderr) back,
* and the deliberate control-flow exceptions -- `ClickException`, `Abort`,
  `Exit`, `CancelledError`, `SystemExit` -- keep their own status and text
  instead of being flattened into the generic failure.

Offline only: every command raises before `upgrade_check` can reach the network,
and each test arms `requests.get` to fail loudly if that ever stops being true.
"""

import asyncio
import subprocess
import sys
from concurrent.futures import CancelledError as FutureCancelledError
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner


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


def _disable_update_request(monkeypatch):
    import praetorian_cli.handlers.cli_decorators as decorators

    request = Mock(side_effect=AssertionError("update check ran after failed command"))
    monkeypatch.setattr(decorators.requests, "get", request)
    return request


# `upgrade_check`'s bare `except:` swallows anything raisable, so an in-process
# guard cannot make a stray network call visible in a child process. `os._exit`
# cannot be caught: if the advisory ever runs, the child's status is 97 and the
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


def test_ordinary_exception_is_redacted_in_normal_mode_and_chained(monkeypatch):
    request = _disable_update_request(monkeypatch)
    cause = RuntimeError("SECRET_UNEXPECTED_SENTINEL")

    result = CliRunner().invoke(
        _command_raising(cause),
        obj=object(),
        standalone_mode=False,
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, click.ClickException)
    assert result.exception.__cause__ is cause
    assert str(result.exception) == "An unexpected error occurred. Re-run with --debug for details."
    assert "SECRET_UNEXPECTED_SENTINEL" not in str(result.exception)
    request.assert_not_called()


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
    assert "An unexpected error occurred" not in result.output
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


def test_real_process_normal_mode_hides_unexpected_traceback_and_message():
    result = _run_child(
        """
import click
from praetorian_cli.handlers.cli_decorators import cli_handler

@click.command()
@cli_handler
def command(_sdk):
    raise RuntimeError("SECRET_UNEXPECTED_SENTINEL")

command.main(obj=object())
"""
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert output == "Error: An unexpected error occurred. Re-run with --debug for details.\n"
    assert "SECRET_UNEXPECTED_SENTINEL" not in output
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
    from praetorian_cli.handlers.cli_decorators import UNEXPECTED_ERROR_MESSAGE

    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_raising(click.Abort()), obj=object())

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert UNEXPECTED_ERROR_MESSAGE not in result.output
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
    assert "An unexpected error occurred" not in result.output
    request.assert_not_called()


def test_sys_exit_passes_through_unchanged(monkeypatch):
    """`SystemExit` is a `BaseException`; the chain must not start catching it."""
    request = _disable_update_request(monkeypatch)

    result = CliRunner().invoke(_command_calling(lambda: sys.exit(7)), obj=object())

    assert result.exit_code == 7
    assert "An unexpected error occurred" not in result.output
    request.assert_not_called()


def test_handled_user_facing_error_is_unchanged(monkeypatch):
    """The *handled* error path is untouched by this change.

    `utils.error` prints `ERROR: <message>` to stderr and exits 1. It must keep
    its own actionable text -- not be redacted -- and must not be re-labelled
    with Click's `Error:` prefix.
    """
    from praetorian_cli.handlers.cli_decorators import UNEXPECTED_ERROR_MESSAGE
    from praetorian_cli.handlers.utils import error

    request = _disable_update_request(monkeypatch)
    command = _command_calling(lambda: error("profile 'staging' is not configured"))

    result = CliRunner().invoke(command, obj=object())

    assert result.exit_code == 1
    assert "ERROR: profile 'staging' is not configured" in result.stderr
    assert UNEXPECTED_ERROR_MESSAGE not in result.output
    request.assert_not_called()


def test_unexpected_error_message_is_a_module_constant():
    """The redacted message must keep its actionable half.

    Redaction without a route to the details is a dead end for the user, so pin
    that the constant still names the flag that recovers them.
    """
    from praetorian_cli.handlers.cli_decorators import UNEXPECTED_ERROR_MESSAGE

    assert "--debug" in UNEXPECTED_ERROR_MESSAGE
