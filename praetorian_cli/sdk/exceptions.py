"""Public exception types raised by the Guard SDK.

The SDK is a library: it reports failures by raising, and never by terminating
the calling process. Before ENG-6570 eight call sites under `praetorian_cli/sdk`
called `praetorian_cli.handlers.utils.error()` instead, whose `exit(1)` raises
`SystemExit` -- a `BaseException`, and therefore invisible to every
`except Exception` an embedder writes. The `except Exception` in
`praetorian_cli/sdk/mcp_server.py` and the ones under `praetorian_cli/ui/` were
all bypassed, so a bad keychain killed those long-lived hosts outright.

Exiting is the CLI's job, and only the CLI's: `@cli_handler`
(`praetorian_cli/handlers/cli_decorators.py`) catches whatever the SDK raises,
surfaces its message, and exits non-zero. Nothing in the SDK catches these.

WHERE TO CHANGE: this module is deliberately message-only -- no attributes, no
error codes, no `__init__` overrides. A public attribute (`.key`, `.profile`,
`.status_code`) is a permanent commitment that can be added later and removed
never, so none is added speculatively. Classification of what is safe to
*display* is ENG-6781, not here.

The hierarchy is sized to what a caller would branch on, not to the number of
call sites:

    GuardError
    +-- ConfigurationError
    +-- AuthenticationError
    +-- NotFoundError
"""


class GuardError(Exception):
    """Base class for every error the Guard SDK raises.

    `except GuardError` is the blanket arm for an embedder that wants to treat
    any SDK failure alike, without also catching unrelated `Exception`s.
    """


class ConfigurationError(GuardError):
    """The local configuration is unusable, so no request can be attempted.

    A missing, corrupted, or incomplete keychain profile. Retrying is pointless:
    the operator has to re-run `praetorian configure` (or set the environment
    variable) before anything else can succeed.
    """


class AuthenticationError(GuardError):
    """The backend rejected the credentials that were sent.

    Distinct from `ConfigurationError` because the local configuration is fine
    and the remote said no: the caller's move is to rotate the key or retry,
    not to reconfigure.
    """


class NotFoundError(GuardError):
    """The requested entity does not exist.

    Ordinary control flow rather than a fault -- a caller walking a list of keys
    writes `except NotFoundError: continue`, which the previous `exit(1)` made
    impossible.
    """
