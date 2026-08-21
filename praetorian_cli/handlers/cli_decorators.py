import errno
import json
import os
import stat
import sys
import tempfile
import threading
import time
from concurrent.futures import CancelledError
from functools import wraps
from importlib.metadata import version
from pathlib import Path

import click
import requests
from packaging.version import InvalidVersion, Version

from praetorian_cli.handlers.utils import error


DEBUG_HINT = "(re-run with --debug for the full traceback)"


def _debug_enabled(ctx):
    return bool(ctx.find_root().params.get("debug", False))


# POLICY: every command routes through this boundary, which surfaces the
# exception's own message -- no sanitizing, summarizing, or redacting. The one
# normalization is outer whitespace: it is trimmed so the appended hint lands on
# the line immediately after the message (and so a whitespace-only message
# counts as blank). The SDK raises bare `Exception`/`ValueError` as its normal
# error-reporting mechanism (`process_failure` in praetorian_cli/sdk/chariot.py,
# praetorian_cli/sdk/entities/*.py), so that message IS the user-facing text.
#
# WHERE TO CHANGE: classification is ENG-6570, redaction is ENG-6781 -- neither
# here. Nor is this the only egress path: praetorian_cli/sdk/mcp_server.py
# returns `str(e)` to its caller, and the SDK is a public library surface.
def _error_message(exc):
    """Surface the exception's own message, plus the `--debug` hint.

    Falls back to the exception's type name when its message is blank.
    """
    message = str(exc).strip() or type(exc).__name__
    return f"{message}\n{DEBUG_HINT}"


def handle_error(func):
    @wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except click.Abort:
            raise
        except Exception as e:
            error(str(e), quit=False)
            if chariot.is_debug:
                click.echo(traceback.format_exc())
        except click.ClickException:
        except click.exceptions.Exit:
        except CancelledError:
        except Exception as exc:
            if _debug_enabled(ctx):
            raise click.ClickException(_error_message(exc)) from exc

    return wrapper


# POLICY: the update advisory is best-effort. It is skipped when the session is
# not interactive, when the opt-out env var is set, and when a group callback is
# merely delegating to a subcommand; it carries no command context (no argv,
# profile, account, or custom headers), bounds its network refresh to
# `UPDATE_CHECK_DEADLINE_SECONDS` of wall clock, and fails open -- no ordinary
# failure of it changes a command outcome. The cache is private where the
# platform enforces POSIX modes: 0700 directory, 0600 file, atomic
# same-directory replace.
#
# POLICY: the throttle record orders SEQUENTIAL invocations only. N truly
# simultaneous ones all read the stale record before any of them writes, so each
# may probe once -- an accepted tradeoff: all of them then write the record, so
# the next TTL is quiet, and the gates above already exclude non-interactive and
# CI sessions, which leaves simultaneous interactive invocations rare. Do NOT
# reintroduce a claim held BY PATH to close it: a claim that cannot identify its
# own holder unlinks a live peer's claim and defeats the rate limit it was built
# to guarantee (measured), and a duplicate refresh costs one CDN-backed GET
# against an already-atomic record write.
#
# WHERE TO CHANGE: cadence, opt-out, endpoint, per-socket timeout, total
# wall-clock deadline, and the sizes a record and a response body may reach
# before they are refused are the constants below; the advisory itself is
# `_check_for_update`.
UPDATE_CHECK_CACHE_MAX_BYTES = 64 * 1024
UPDATE_CHECK_CACHE_TTL_SECONDS = 24 * 60 * 60
UPDATE_CHECK_DEADLINE_SECONDS = 3
UPDATE_CHECK_DISABLE_ENV = "PRAETORIAN_CLI_DISABLE_UPDATE_CHECK"
UPDATE_CHECK_DISABLE_VALUES = frozenset({"1", "true", "yes", "on"})
UPDATE_CHECK_NON_INTERACTIVE_ENV = ("CI", "GITHUB_ACTIONS")
UPDATE_CHECK_RESPONSE_MAX_BYTES = 1024 * 1024
UPDATE_CHECK_TIMEOUT_SECONDS = 2
UPDATE_CHECK_URL = "https://pypi.org/pypi/praetorian-cli/json"


def _session_is_interactive():
    """True only when a human is plausibly watching this invocation.

    BOTH streams must be a terminal. An stderr-only gate does not hold: in
    `guard list assets | jq` only stdout is redirected, so stderr stays a tty
    and the advisory still fires -- the piped, scripted, high-volume case whose
    cadence this is supposed to stop leaking. `CI`/`GITHUB_ACTIONS`/`TERM=dumb`
    cover the runners that allocate a pty anyway.
    """
    try:
        if not (sys.stdout.isatty() and sys.stderr.isatty()):
            return False
    except Exception:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return not any(os.environ.get(name) for name in UPDATE_CHECK_NON_INTERACTIVE_ENV)


def _update_check_disabled():
    """Accept any conventional truthy value, not only `1`.

    This is a privacy opt-out: a user who exports `=true` and still gets network
    requests has been silently overruled by a parsing detail.
    """
    return os.environ.get(UPDATE_CHECK_DISABLE_ENV, "").strip().lower() in UPDATE_CHECK_DISABLE_VALUES


def _delegating_to_subcommand():
    """True when this callback is a group about to invoke a subcommand.

    Click runs a group callback BEFORE its subcommand (measured), so an advisory
    printed here precedes the work the user asked for, and still prints when that
    subcommand goes on to fail. The leaf command runs its own check, so skipping
    here loses nothing -- and it needs no hand-maintained command list.
    """
    ctx = click.get_current_context(silent=True)
    return ctx is not None and ctx.invoked_subcommand is not None


def _update_check_cache_path():
    cache_home = os.environ.get("XDG_CACHE_HOME")
    # POLICY: a relative `XDG_CACHE_HOME` is ignored, as the XDG base-directory
    # spec requires. Honouring one resolves the cache against the current working
    # directory, so every invocation from a different directory sees a cold cache
    # and re-probes. An empty value is falsy and already falls back here.
    if cache_home and not Path(cache_home).is_absolute():
        cache_home = None
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "praetorian-cli" / "update-check.json"


def _path_is_owned_by_effective_user(path):
    """True when `path` belongs to us -- and on platforms that have no uids.

    POLICY: `os.geteuid` is POSIX-only, so its absence must read as "owned"
    rather than take the advisory down; an unguarded POSIX-only call has done
    the latter here once already.
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return True
    return path.stat().st_uid == geteuid()


def _parse_version(raw):
    """A `Version`, or None when the value is absent or unparseable.

    Returning None rather than raising is what keeps a malformed PyPI payload
    from killing the advisory through the fail-open arm (measured: an
    unparseable release key took the advisory from 0 to 1). It does not shorten
    a blackout: a fresh entry short-circuits the refresh whether or not its
    version parsed, and such an entry stays silent until its TTL expires -- at
    which point it does recover.
    """
    if not isinstance(raw, str):
        return None
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def _read_update_check_cache(cache_path):
    """`(checked_at, latest_version_or_None)`, or None when there is no usable record.

    A record with a null or unparseable version is still returned: it throttles.

    POLICY: the record is opened by DESCRIPTOR and validated before a byte of it
    is read. Nothing has vetted this path yet -- on a cold cache this is the
    first thing in the module to touch it -- and a plain `open` here trusts
    whatever is sitting at the path: it blocks in the kernel forever on a planted
    FIFO, raising no `OSError` for either fail-open arm to catch, and hands
    `json.load` an unbounded read of a device or an oversized file. `O_NONBLOCK`
    refuses the FIFO, `O_NOFOLLOW` the symlink, `S_ISREG` a device reached any
    other way, the size cap the oversized regular file, and the uid check a
    record planted by another user. Every refusal is raised as an `OSError`, so
    the arm below already reads it as "no usable record".

    POLICY: the `fstat` size check is the cheap first line of defence, not the
    enforcement -- it describes the file as of the stat, and the read that
    follows is a separate syscall on the same descriptor. So the read is bounded
    too: at most `UPDATE_CHECK_CACHE_MAX_BYTES + 1` bytes, and one byte over the
    ceiling is refused as `EFBIG` for the arm below (measured: an unbounded
    `json.load` on a descriptor whose file grew after the stat yielded 8 MiB
    against a 64 KiB cap).

    WHERE TO CHANGE: the ceiling is `UPDATE_CHECK_CACHE_MAX_BYTES`, and it counts
    BYTES -- the descriptor is read in binary and `json.loads` decodes UTF-8
    itself, so a multi-byte record cannot spend more than the ceiling. On Windows
    both `os.open` flags degrade to 0 and `O_BINARY` stays unset, which is
    JSON-insensitive (the writer emits no newlines); the type, size, and
    ownership checks still hold there.
    """
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(cache_path, flags)
        # `os.fdopen` owns the descriptor only once it returns; until then this is
        # the only reference to it, so every exit but success closes it here.
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise OSError(errno.EINVAL, "cache record is not a regular file")
            if info.st_size > UPDATE_CHECK_CACHE_MAX_BYTES:
                raise OSError(errno.EFBIG, "cache record is too large")
            geteuid = getattr(os, "geteuid", None)
            if geteuid is not None and info.st_uid != geteuid():
                raise OSError(errno.EPERM, "cache record is not owned by us")
            cache_file = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
        with cache_file:
            record = cache_file.read(UPDATE_CHECK_CACHE_MAX_BYTES + 1)
        if len(record) > UPDATE_CHECK_CACHE_MAX_BYTES:
            raise OSError(errno.EFBIG, "cache record is too large")
        cache = json.loads(record)
        checked_at = cache["checked_at"]
        if isinstance(checked_at, bool) or not isinstance(checked_at, (int, float)):
            return None
        return checked_at, _parse_version(cache.get("latest_version"))
    except (KeyError, OSError, TypeError, ValueError):
        return None


def _update_check_cache_is_fresh(cached, now):
    """True when `cached` is a usable record still inside the TTL.

    POLICY: a `checked_at` in the future is stale, not fresh, so a bad clock
    cannot pin a stale answer forever.
    """
    return cached is not None and 0 <= now - cached[0] < UPDATE_CHECK_CACHE_TTL_SECONDS


def _cache_dir_descriptor_supported():
    """True when the leaf directory can be validated and re-moded through one descriptor.

    POLICY: `O_NOFOLLOW` and `os.fchmod` are POSIX-only, and an unguarded
    POSIX-only call has taken this advisory down once already, so their absence
    selects the path-based arm instead of raising. `O_DIRECTORY` is POSIX-only
    too but needs no guard of its own: the explicit `S_ISDIR` check is what the
    decision rests on, on every platform.
    """
    return hasattr(os, "O_NOFOLLOW") and hasattr(os, "fchmod")


def _open_update_check_cache_dir(cache_path):
    """An open descriptor on the leaf cache directory, locked to 0700, or None.

    POLICY: validate and re-mode ONE inode -- the one this descriptor addresses.
    A path-based `is_symlink()` check followed by a path-based `chmod` resolves
    the leaf twice, and swapping it for a symlink in between aims the 0700 repair
    at a directory that is none of our business; `os.fstat` and `os.fchmod` cannot
    be redirected that way. `O_NOFOLLOW` covers the FINAL component only, which is
    exactly the leaf-only scope this module holds to: a symlinked `~/.cache`
    ANCESTOR is a legitimate, common dotfile setup and keeps working. A directory
    we do not own is refused rather than repaired.

    WHERE TO CHANGE: the descriptor is the caller's to close, and a caller that
    goes on to write inside the directory addresses its files with `dir_fd=`
    rather than resolving the path a second time. Any `OSError` means None.
    """
    parent = cache_path.parent
    try:
        try:
            parent.mkdir(parents=True, mode=0o700)
        except FileExistsError:
            pass
        fd = os.open(parent, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise OSError(errno.ENOTDIR, "cache directory is not a directory")
        geteuid = getattr(os, "geteuid", None)
        if geteuid is not None and info.st_uid != geteuid():
            raise OSError(errno.EPERM, "cache directory is not owned by us")
        # mkdir's mode is masked by umask; the fchmod is what guarantees the mode.
        os.fchmod(fd, 0o700)
    except OSError:
        os.close(fd)
        return None
    except BaseException:
        os.close(fd)
        raise
    return fd


def _prepare_update_check_cache_dir(cache_path):
    """Create the cache directory and lock it to 0700. True only when writing there is safe.

    POLICY: the LEAF directory only -- the `praetorian-cli` directory this
    creates. A symlinked `~/.cache` is a legitimate, common dotfile setup and
    must keep working, so do NOT widen this to ancestors. Following a symlinked
    leaf would chmod and write inside whatever directory someone else pointed it
    at, and a path we did not create is only ours to repair when it is a
    directory we own.

    WHERE TO CHANGE: this runs before the throttle record is written (the record
    needs a directory to be created in) and again inside
    `_write_update_check_cache`, which validates on its own terms rather than
    trusting its caller -- and which keeps the descriptor this discards. The
    path-based arm below is the fallback for platforms that cannot close the
    two-resolution window at all.
    """
    try:
        if _cache_dir_descriptor_supported():
            dir_fd = _open_update_check_cache_dir(cache_path)
            if dir_fd is None:
                return False
            os.close(dir_fd)
            return True
        parent = cache_path.parent
        if parent.is_symlink():
            return False
        try:
            parent.mkdir(parents=True, mode=0o700)
            created = True
        except FileExistsError:
            created = False
        if not created and not (parent.is_dir() and _path_is_owned_by_effective_user(parent)):
            return False
        # mkdir's mode is masked by umask; the chmod is what guarantees the mode.
        parent.chmod(0o700)
        return True
    except CancelledError:
        raise
    except Exception:
        return False


def _write_update_check_record_at(dir_fd, name, payload):
    """Atomically write `payload` to `name` inside the directory `dir_fd` addresses.

    POLICY: every step names the validated directory by descriptor, never by
    path, so the destination cannot be swapped between the check and the write.
    `os.rename` and not `os.replace`: measured, `os.replace` is absent from
    `os.supports_dir_fd` on platforms where `os.open` and `os.rename` are
    present, and a same-directory rename overwrites atomically either way.
    `tempfile.mkstemp` has no `dir_fd`, so the temporary is created here --
    `O_EXCL` against a random name, 0600 from the start as `mkstemp` does it,
    and `os.fchmod` to hold that mode under any umask.
    """
    temp_name = f"{name}.{os.urandom(8).hex()}.tmp"
    fd = os.open(temp_name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=dir_fd)
    try:
        # `os.fdopen` takes ownership of the descriptor only once it returns, so a
        # failure inside it leaves the descriptor with no owner at all; the
        # `finally` below reclaims the temporary's PATH, never a DESCRIPTOR.
        # `BaseException`, because a KeyboardInterrupt landing here leaks
        # identically.
        try:
            temp_file = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with temp_file:
            os.fchmod(temp_file.fileno(), 0o600)
            json.dump(payload, temp_file)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.rename(temp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    finally:
        try:
            os.unlink(temp_name, dir_fd=dir_fd)
        except FileNotFoundError:
            pass


def _write_update_check_record_by_path(cache_path, payload):
    """Atomically write `payload` to `cache_path`, resolving it by path.

    The fallback for platforms with no directory descriptor. `mkstemp` creates
    the file 0600 regardless of umask (measured at `umask 0000`), which is why no
    `os.fchmod` follows it: `os.fchmod` is POSIX-only, and on Windows its
    AttributeError was swallowed by the fail-open arm -- taking the whole
    advisory down with it, every run.
    """
    # Same directory as the destination, so `os.replace` is an atomic rename.
    fd, temp_name = tempfile.mkstemp(dir=cache_path.parent)
    temp_path = Path(temp_name)
    try:
        # As above: `os.fdopen` owns the descriptor only once it returns, and the
        # `finally` reclaims the path rather than the descriptor.
        try:
            temp_file = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with temp_file:
            json.dump(payload, temp_file)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, cache_path)
        cache_path.chmod(0o600)
    finally:
        temp_path.unlink(missing_ok=True)


def _write_update_check_cache(cache_path, checked_at, latest_version):
    """Record an attempt. True on success, False when this environment cannot.

    The contract, spelled out because this one write is load-bearing for three
    unrelated properties:

    * It VALIDATES THE DESTINATION before touching it, whatever its caller
      already did -- and on the descriptor arm it writes THROUGH the descriptor
      it validated, so the directory it vetted is the directory it writes in.
    * It lets NOTHING ESCAPE. No descriptor and no temporary file survives any
      failure path, including a failure raised between the temporary's creation
      and the `os.fdopen` that takes ownership of its descriptor.
    * It is NO PART of any exclusion between concurrent refreshes -- there is
      none, by policy (see the module POLICY block). Simultaneous invocations
      each reach this function and each write; the write is an atomic
      same-directory rename, so the record a reader sees is always one writer's
      whole record.
    * `False` means "this environment cannot be throttled, so do not probe".
      Returns rather than raises: the caller treats a failed write as a
      control-flow signal (stay off the network), not as an error to swallow.
    """
    try:
        payload = {
            "checked_at": checked_at,
            "latest_version": None if latest_version is None else str(latest_version),
        }
        if _cache_dir_descriptor_supported():
            dir_fd = _open_update_check_cache_dir(cache_path)
            if dir_fd is None:
                return False
            try:
                _write_update_check_record_at(dir_fd, cache_path.name, payload)
            finally:
                os.close(dir_fd)
            return True
        if not _prepare_update_check_cache_dir(cache_path):
            return False
        _write_update_check_record_by_path(cache_path, payload)
        return True
    except CancelledError:
        raise
    except Exception:
        return False


def _fetch_latest_version():
    """PyPI's own latest STABLE release, or None when the payload is unusable.

    `info.version` rather than `max(Version(r) for r in releases)`: the max over
    release keys ranks prereleases above stable ones (2.0.0rc1 over 1.0.0), and a
    single unparseable key raises `InvalidVersion` into the fail-open arm.

    POLICY: the GET asks for no compression and the body is bounded by the RAW
    bytes read off the socket, so raw and decoded are the same bytes. The cap has
    to hold on EVERY urllib3 the `requests` pin permits, and only the raw read is
    bounded on all of them: `decode_content=True` bounds DECODED bytes on urllib3
    >= 2, but on 1.26.x it reads that many ENCODED bytes and then decompresses
    without any bound -- a wire-bytes cap, which a gzip bomb walks straight
    through (measured, 55 KiB of wire peaking 131x past this 1 MiB ceiling). A
    server that ignores the header and compresses anyway is still capped at the
    raw read, and `json.loads` then raises on the compressed bytes into the
    fail-open arm -- no advisory, which is the intended outcome, so a
    `Content-Encoding` check would add a branch and change no behaviour.
    `Content-Length` cannot stand in for the cap either: measured, this endpoint
    answers `Content-Length: 28568` for a body of 117712 bytes when it gzips, and
    a header describes what a server claims it will send, not what arrives.

    WHERE TO CHANGE: the ceiling is `UPDATE_CHECK_RESPONSE_MAX_BYTES`, it counts
    RAW bytes, and the oversize arm must return BEFORE parsing. The real payload
    is 115 KiB across 64 releases (~1.8 KiB per release), so the 1 MiB ceiling
    keeps ~8.9x of headroom that grows with the release count. `json.loads` takes
    the undecoded `bytes` and detects UTF-8 itself, so no decoding step belongs
    here. The response is closed on every path: `stream=True` holds the
    connection open until it is.
    """
    response = requests.get(UPDATE_CHECK_URL, timeout=UPDATE_CHECK_TIMEOUT_SECONDS, stream=True,
                            headers={"Accept-Encoding": "identity"})
    with response:
        response.raise_for_status()
        body = response.raw.read(UPDATE_CHECK_RESPONSE_MAX_BYTES + 1, decode_content=False)
    if len(body) > UPDATE_CHECK_RESPONSE_MAX_BYTES:
        return None
    return _parse_version(json.loads(body)["info"]["version"])


def _fetch_latest_version_within_deadline():
    """`_fetch_latest_version`'s answer, or None when it does not land in time.

    POLICY: the refresh gets a hard WALL-CLOCK bound. `requests`' `timeout`
    bounds each individual socket operation and never the total -- measured, a
    `timeout=2` GET against a server dribbling one header byte every 1.5s
    returned after 64.7 seconds, and the real CLI sat alive 10.1s past its own
    last line of output. So the fetch runs on a thread and a thread still alive
    after the join is ABANDONED, its result discarded. `daemon=True` is
    load-bearing: the interpreter must not wait for an abandoned fetch at exit.
    For the same reason this is a bare thread and NOT a
    `concurrent.futures.ThreadPoolExecutor`, whose `atexit` handler joins its
    workers and would reinstate exactly the wait this removes.

    WHERE TO CHANGE: the bound is `UPDATE_CHECK_DEADLINE_SECONDS`; the per-socket
    `UPDATE_CHECK_TIMEOUT_SECONDS` still applies inside the thread and still
    helps the common case -- this is the outer guarantee, not its replacement.
    """
    fetched = [None]

    def fetch():
        # Nothing may escape a thread nobody is waiting for any more: an
        # exception here would reach the interpreter's excepthook and print over
        # the command's own output.
        try:
            fetched[0] = _fetch_latest_version()
        except BaseException:
            pass

    thread = threading.Thread(target=fetch, daemon=True)
    thread.start()
    thread.join(UPDATE_CHECK_DEADLINE_SECONDS)
    return None if thread.is_alive() else fetched[0]


def _check_for_update():
    try:
        if _update_check_disabled():
            return
        if not _session_is_interactive():
            return
        if _delegating_to_subcommand():
            return
        now = time.time()
        cache_path = _update_check_cache_path()
        cached = _read_update_check_cache(cache_path)
        latest = cached[1] if cached is not None else None
        if not _update_check_cache_is_fresh(cached, now):
            # The record below is written IN the cache directory, so the directory
            # has to exist and be trustworthy first. Failing to prepare it is the
            # same signal a failed record write is: an environment whose probe
            # rate we cannot limit is one we must not probe.
            if not _prepare_update_check_cache_dir(cache_path):
                return
            # Record the attempt BEFORE making it, so EVERY way a refresh can
            # fail is throttled by the same record -- network and HTTP errors, an
            # unparseable payload, a body over the size ceiling, a fetch
            # abandoned at the deadline, and the environments where the cache
            # cannot be written at all (a read-only filesystem, a cache directory
            # owned by another user). A file-based cache written only on success
            # cannot throttle the case where the file cannot be written, which is
            # how this reached pypi.org on every single invocation. The previous
            # known version rides along, so a failed refresh keeps advertising
            # what we already knew.
            if not _write_update_check_cache(cache_path, now, latest):
                return
            try:
                fetched = _fetch_latest_version_within_deadline()
            except CancelledError:
                raise
            except Exception:
                fetched = None
            if fetched is not None:
                latest = fetched
                _write_update_check_cache(cache_path, now, latest)
        if latest is None:
            return
        local = Version(version('praetorian-cli'))
        if latest > local:
            click.echo(f'A new version of praetorian-cli is available: {latest}', err=True)
            click.echo(f'You are currently running {local}.', err=True)
            click.echo('To upgrade, run "pip install --upgrade praetorian-cli".', err=True)
    except CancelledError:
        raise
    # `Exception`, not a bare `except`: KeyboardInterrupt and SystemExit derive
    # from BaseException, so they keep propagating instead of being swallowed.
    except Exception:
        pass


def upgrade_check(func):
    # POLICY: the advisory is an epilogue to work whose output has ALREADY been
    # produced, and this decorator composes OUTERMOST -- outside `handle_error`
    # -- so anything escaping here becomes the command's exit status. A Ctrl-C
    # during the advisory therefore must not turn a completed command into
    # `Aborted!` and exit 1: a non-zero exit for work that already succeeded
    # invites an unsafe retry of a mutating command (measured: 968 rows
    # delivered, then exit 1).
    #
    # WHERE TO CHANGE: `CancelledError` is deliberately NOT caught here, and the
    # asymmetry with `KeyboardInterrupt` is not an oversight -- a cancelled async
    # task must still observe its cancellation, so it keeps propagating exactly
    # as `_check_for_update`'s own `except CancelledError: raise` arm sends it.
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            _check_for_update()
        except KeyboardInterrupt:
            pass
        return result

    return wrapper

def cli_handler(func):
    func = click.pass_obj(func)
    func = handle_error(func)
    func = upgrade_check(func)
    return func


def list_params(filter_by, has_details=True, has_filter=True, has_type=False):
    def decorator(func):
        func = pagination(func)
        func = cli_handler(func)
        if has_filter:
            func = click.option('-f', '--filter', default='', help=f'Filter by {filter_by}')(func)
        if has_details:
            func = click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')(func)
        if has_type:
            func = click.option('-t', '--type', "model_type", default='', help='Select only a subset by type')(func)
        return func

    return decorator


def pagination(func):
    func = click.option('-o', '--offset', default=0, help='List results from an offset')(func)
    func = click.option('-p', '--page', type=click.Choice(('first', 'all')), default='first',
                        help='Pagination mode. "all" pages up to 10,000 pages.', show_default=True)(func)
    return func

def praetorian_only(func):
    @wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        if not ctx.obj.is_praetorian_user():
            error("This option is limited to Praetorian engineers only. Please contact your Praetorian representative for assistance.")
        return func(*args, **kwargs)
    return wrapper
