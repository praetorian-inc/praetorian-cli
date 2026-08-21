# Marcus Terminal Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Marcus AI console mode correct (no sticky impersonation, no swallowed errors, clean Ctrl-C), efficient (paged polling with idle backoff), and pleasant (Rich `Live` streaming), with real test coverage.

**Architecture:** Refactor `_send_to_marcus` into focused units — `_post_to_planner` (POST + 403 retry inside a `try/finally` impersonation guard + guarded JSON parse), `_poll_messages` (paged fetch + backoff, surfaces real errors), `_render_stream` (Rich `Live`). Public command surface (`ask`, `marcus`, `marcus read/ingest/do`, `research`) is unchanged.

**Tech Stack:** Python 3.12, Rich (`Live`), prompt_toolkit, pytest. SDK: `sdk.chariot_request`, `sdk.search.by_key_prefix`, `sdk.accounts.login_principal`, `sdk.keychain.account`.

**Branch:** `fix/marcus-terminal` (new, off `main`). Base spec: `docs/superpowers/specs/2026-05-28-marcus-terminal-design.md`.

---

## File Structure

- Modify: `praetorian_cli/ui/console/commands/marcus.py` — split `_send_to_marcus`; add `_post_to_planner`, `_poll_messages`, `_render_stream`.
- Test: `praetorian_cli/sdk/test/ui/test_console_marcus.py` (new).

The Marcus parsing helpers (`_parse_tool_name`, `_parse_tool_result`, `_infer_tool_from_response`) stay as-is but become directly unit-tested.

---

## Task 1: Test harness + parsing coverage (characterization)

**Files:**
- Create: `praetorian_cli/sdk/test/ui/test_console_marcus.py`

- [ ] **Step 1: Write characterization tests for the parsing helpers**

```python
# praetorian_cli/sdk/test/ui/test_console_marcus.py
import json
import types
import pytest
from praetorian_cli.ui.console.commands.marcus import MarcusCommands


class _Host(MarcusCommands):
    """Bare host exposing MarcusCommands methods for unit testing."""
    def __init__(self):
        pass


@pytest.fixture
def host():
    return _Host()


def test_parse_tool_name_from_structured_content(host):
    content = json.dumps({'name': 'run_capability', 'input': {'capability': 'nuclei'}})
    assert host._parse_tool_name(content, {}) == 'run_capability(nuclei)'

def test_parse_tool_name_falls_back_to_tool(host):
    assert host._parse_tool_name('not json', {}) == 'tool'

def test_parse_tool_result_counts_list(host):
    content = json.dumps({'assets': [1, 2, 3]})
    assert host._parse_tool_result(content) == '3 assets'

def test_infer_tool_from_response_status(host):
    assert host._infer_tool_from_response(json.dumps({'status': 'JF'})) == 'status_check'
```

- [ ] **Step 2: Run tests to verify they pass (characterization — should already pass)**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -v`
Expected: PASS. These pin current behavior before refactoring.

- [ ] **Step 3: Commit**

```bash
git add praetorian_cli/sdk/test/ui/test_console_marcus.py
git commit -m "test(marcus): characterization tests for tool-name/result parsing"
```

---

## Task 2: Fix impersonation restore (try/finally)

**Files:**
- Modify: `praetorian_cli/ui/console/commands/marcus.py:106-137`
- Test: `praetorian_cli/sdk/test/ui/test_console_marcus.py`

- [ ] **Step 1: Write the failing test**

```python
class _FakeResp:
    def __init__(self, status, body='', payload=None, ok=None):
        self.status_code = status
        self.text = body
        self._payload = payload if payload is not None else {}
        self.ok = ok if ok is not None else (200 <= status < 300)
    def json(self):
        return self._payload


def _make_host_for_post(first_resp, second_resp=None, login='analyst@praetorian.com'):
    host = _Host()
    calls = {'n': 0}
    class _KC: account = 'client@acme.com'
    class _Accounts:
        def login_principal(self): return login
    class _SDK:
        keychain = _KC()
        accounts = _Accounts()
        def url(self, p): return 'https://x' + p
        def chariot_request(self, method, url, json=None):
            calls['n'] += 1
            if calls['n'] == 1:
                if isinstance(first_resp, Exception):
                    raise first_resp
                return first_resp
            return second_resp
    host.sdk = _SDK()
    host.context = types.SimpleNamespace(account='client@acme.com', mode='agent',
                                         conversation_id=None)
    class _Console:
        def print(self, *a, **k): pass
        def status(self, *a, **k):
            import contextlib
            return contextlib.nullcontext()
    host.console = _Console()
    host.colors = {'primary': 'red'}
    return host, calls


def test_impersonation_restored_after_exception(host):
    h, calls = _make_host_for_post(RuntimeError('boom'))
    with pytest.raises(RuntimeError):
        h._post_to_planner('hello')
    # keychain.account must be restored even though the call raised
    assert h.sdk.keychain.account == 'client@acme.com'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k impersonation -v`
Expected: FAIL with `AttributeError: ... has no attribute '_post_to_planner'`.

- [ ] **Step 3: Extract `_post_to_planner` with try/finally + guarded JSON**

Add to `MarcusCommands` and replace the POST/403-retry/JSON-parse portion of `_send_to_marcus` (lines ~106-141) with a call to it:

```python
    def _post_to_planner(self, message: str):
        """POST to /planner, handling the 403 retry-as-Praetorian path safely.

        Returns the parsed JSON dict. Raises on network error; the keychain
        account is always restored.
        """
        url = self.sdk.url('/planner')
        payload = {'message': message, 'mode': self.context.mode}
        if self.context.conversation_id:
            payload['conversationId'] = self.context.conversation_id

        with self.console.status('Sending...', spinner='dots',
                                 spinner_style=self.colors['primary']):
            response = self.sdk.chariot_request('POST', url, json=payload)

        if response.status_code == 403 and self.context.account:
            login_user = self.sdk.accounts.login_principal()
            if login_user and login_user.endswith('@praetorian.com'):
                self.console.print(
                    f'[dim]AI not enabled on this account -- routing through {login_user}[/dim]')
                saved_account = self.sdk.keychain.account
                try:
                    self.sdk.keychain.account = None
                    if self.context.account not in message:
                        message = f'[Context: querying data for account {self.context.account}] {message}'
                    payload['message'] = message
                    if self.context.conversation_id:
                        payload.pop('conversationId', None)
                        self.context.conversation_id = None
                    with self.console.status('Sending via Praetorian account...', spinner='dots',
                                             spinner_style=self.colors['primary']):
                        response = self.sdk.chariot_request('POST', url, json=payload)
                finally:
                    self.sdk.keychain.account = saved_account

        if not response.ok:
            raise MarcusError(f'API error: {response.status_code} - {response.text}')

        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            raise MarcusError(
                f'Unexpected non-JSON response ({response.status_code}): {response.text[:200]}')
```

Add a small exception type near the top of the module:

```python
class MarcusError(Exception):
    """Raised for recoverable Marcus terminal errors (shown to the user)."""
```

Update `_send_to_marcus` to call `_post_to_planner` and convert `MarcusError` into the existing user-facing error print + `return None`:

```python
        try:
            result = self._post_to_planner(message)
        except MarcusError as e:
            self.console.print(f'[error]{e}[/error]')
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k impersonation -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/ui/console/commands/marcus.py praetorian_cli/sdk/test/ui/test_console_marcus.py
git commit -m "fix(marcus): restore impersonation in finally; guard non-JSON responses"
```

---

## Task 3: Guarded JSON + 403 retry routing test

**Files:**
- Test: `praetorian_cli/sdk/test/ui/test_console_marcus.py`

- [ ] **Step 1: Write the tests**

```python
def test_non_json_response_raises_marcus_error(host):
    from praetorian_cli.ui.console.commands.marcus import MarcusError
    bad = _FakeResp(500, body='<html>oops</html>')
    def _json(): raise ValueError('no json')
    bad.json = _json
    h, _ = _make_host_for_post(bad)
    with pytest.raises(MarcusError):
        h._post_to_planner('hi')

def test_403_retries_through_praetorian_account(host):
    first = _FakeResp(403, body='forbidden')
    second = _FakeResp(200, payload={'conversation': {'uuid': 'c1'}})
    h, calls = _make_host_for_post(first, second)
    out = h._post_to_planner('hi')
    assert calls['n'] == 2
    assert out['conversation']['uuid'] == 'c1'
    assert h.sdk.keychain.account == 'client@acme.com'  # restored
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k "non_json or retries" -v`
Expected: PASS (behavior implemented in Task 2).

- [ ] **Step 3: Commit**

```bash
git add praetorian_cli/sdk/test/ui/test_console_marcus.py
git commit -m "test(marcus): cover non-JSON and 403 retry routing"
```

---

## Task 4: Paged polling with idle backoff + surfaced errors

**Files:**
- Modify: `praetorian_cli/ui/console/commands/marcus.py` (the poll loop, lines ~143-230)
- Test: `praetorian_cli/sdk/test/ui/test_console_marcus.py`

- [ ] **Step 1: Write the failing test**

```python
def test_poll_messages_yields_only_new_and_stops_on_chariot(host):
    msgs_round1 = [{'key': '#message#c1#001', 'role': 'tool call', 'content': '{}'},
                   {'key': '#message#c1#002', 'role': 'tool response', 'content': '{"assets":[1]}'}]
    msgs_round2 = msgs_round1 + [{'key': '#message#c1#003', 'role': 'chariot', 'content': 'final answer'}]
    rounds = iter([msgs_round1, msgs_round2])
    class _Search:
        def by_key_prefix(self, prefix, user=False):
            return (next(rounds), None)
    host.sdk = types.SimpleNamespace(search=_Search())
    host.context = types.SimpleNamespace(verbose=False)
    collected = list(host._poll_messages('c1', after_key='', max_wait=5, sleep=lambda s: None))
    roles = [m['role'] for m in collected]
    assert roles[-1] == 'chariot'
    assert collected[-1]['content'] == 'final answer'

def test_poll_messages_surfaces_persistent_errors(host):
    class _Search:
        def by_key_prefix(self, prefix, user=False):
            raise RuntimeError('search down')
    host.sdk = types.SimpleNamespace(search=_Search())
    host.context = types.SimpleNamespace(verbose=False)
    from praetorian_cli.ui.console.commands.marcus import MarcusError
    with pytest.raises(MarcusError):
        list(host._poll_messages('c1', after_key='', max_wait=2, sleep=lambda s: None,
                                 error_threshold=1))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k poll_messages -v`
Expected: FAIL with `AttributeError: ... has no attribute '_poll_messages'`.

- [ ] **Step 3: Implement `_poll_messages` as a generator**

Add to `MarcusCommands`:

```python
    def _poll_messages(self, conversation_id, after_key='', *, max_wait=180,
                       sleep=time.sleep, error_threshold=5):
        """Yield new conversation messages in key order until a 'chariot' reply.

        Pages by after_key (client-side filter today; server-side if supported).
        Backs off when idle. Raises MarcusError after `error_threshold`
        consecutive fetch failures so problems surface instead of hanging.
        """
        start = time.time()
        last_key = after_key
        delay = 1.0
        consecutive_errors = 0
        prefix = f'#message#{conversation_id}#'
        while time.time() - start < max_wait:
            try:
                messages, _ = self.sdk.search.by_key_prefix(prefix, user=True)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= error_threshold:
                    raise MarcusError(f'Lost connection while waiting for Marcus: {e}')
                sleep(delay)
                continue
            new = sorted((m for m in messages if m.get('key', '') > last_key),
                         key=lambda x: x.get('key', ''))
            if new:
                delay = 1.0  # reset backoff on activity
                for msg in new:
                    last_key = msg.get('key', '')
                    yield msg
                    if msg.get('role', '') == 'chariot':
                        return
            else:
                delay = min(delay + 1.0, 3.0)  # idle backoff
            sleep(delay)
        raise MarcusError('Timed out waiting for response')
```

Rewrite the poll section of `_send_to_marcus` to consume this generator (preserving the existing snapshot of `last_key` and the tool-log rendering), and convert a trailing-timeout `MarcusError` into the existing `[warning]Timed out…[/warning]` + `return None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k poll_messages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/ui/console/commands/marcus.py praetorian_cli/sdk/test/ui/test_console_marcus.py
git commit -m "perf(marcus): paged polling generator with idle backoff and surfaced errors"
```

---

## Task 5: Rich Live streaming + graceful Ctrl-C

**Files:**
- Modify: `praetorian_cli/ui/console/commands/marcus.py`
- Test: `praetorian_cli/sdk/test/ui/test_console_marcus.py`

- [ ] **Step 1: Write the failing test**

```python
def test_send_to_marcus_handles_ctrl_c(host, monkeypatch):
    # _post_to_planner succeeds, but polling raises KeyboardInterrupt
    host._post_to_planner = lambda m: {'conversation': {'uuid': 'c1'}}
    def _boom(*a, **k):
        raise KeyboardInterrupt()
    host._poll_messages = _boom
    class _Console:
        printed = []
        def print(self, *a, **k): _Console.printed.append(' '.join(str(x) for x in a))
        def status(self, *a, **k):
            import contextlib; return contextlib.nullcontext()
    host.console = _Console()
    host.colors = {'primary': 'red'}
    host.context = types.SimpleNamespace(account=None, mode='agent', conversation_id=None,
                                         verbose=False)
    class _Search:
        def by_key_prefix(self, prefix, user=False): return ([], None)
    host.sdk = types.SimpleNamespace(search=_Search())
    result = host._send_to_marcus('hi')
    assert result is None
    assert any('cancel' in p.lower() or 'interrupt' in p.lower() for p in _Console.printed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -k ctrl_c -v`
Expected: FAIL (KeyboardInterrupt propagates; no cancel message).

- [ ] **Step 3: Wrap the poll consumption in try/except KeyboardInterrupt**

In `_send_to_marcus`, surround the `_poll_messages` consumption with:

```python
        try:
            for msg in self._poll_messages(self.context.conversation_id, after_key=last_key):
                ...  # existing per-role rendering; return content on 'chariot'
        except KeyboardInterrupt:
            self.console.print('\n[warning]Cancelled — returned to console.[/warning]')
            return None
        except MarcusError as e:
            self.console.print(f'\n[warning]{e}[/warning]')
            return None
```

- [ ] **Step 4: Replace the `\r` rewrite with a Rich Live region**

Within that loop, render tool activity and incremental assistant text through a `rich.live.Live` region instead of the carriage-return rewrite at the old line ~215. Keep the `tool_log`/`_last_tool_log` bookkeeping intact for the `show tools` command. Minimal shape:

```python
        from rich.live import Live
        from rich.console import Group
        lines = []
        with Live(console=self.console, refresh_per_second=8, transient=False) as live:
            for msg in self._poll_messages(...):
                role = msg.get('role', '')
                if role == 'tool call':
                    name = self._parse_tool_name(msg.get('content', ''), msg)
                    lines.append(f'  [dim]->[/dim] [accent]{name}[/accent] …')
                elif role == 'tool response':
                    summary = self._parse_tool_result(msg.get('content', ''))
                    if lines:
                        lines[-1] = lines[-1].replace(' …', f' [dim]-- {summary}[/dim] [success]done[/success]')
                elif role == 'chariot':
                    self._last_tool_log = tool_log
                    return msg.get('content', '')
                live.update(Group(*[__import__('rich').text.Text.from_markup(l) for l in lines]))
```

(Preserve verbose-mode expansion via the existing `_print_verbose_*` helpers when `self.context.verbose`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_marcus.py -v`
Expected: PASS (all Marcus tests).

- [ ] **Step 6: Manual smoke (requires auth)**

```bash
guard            # launch console
marcus           # enter conversation mode
> what assets do I have?     # observe live tool activity + streamed answer; Ctrl-C mid-run returns cleanly
/back
```

- [ ] **Step 7: Commit**

```bash
git add praetorian_cli/ui/console/commands/marcus.py praetorian_cli/sdk/test/ui/test_console_marcus.py
git commit -m "feat(marcus): Rich Live streaming and graceful Ctrl-C handling"
```

---

## Task 6: Full suite + regression check

**Files:**
- Test only.

- [ ] **Step 1: Run the full UI suite**

Run: `pytest praetorian_cli/sdk/test/ui/ -q`
Expected: green. Fix any test coupled to the old `_send_to_marcus` internals.

- [ ] **Step 2: Commit any fixups**

```bash
git add -A && git commit -m "test(marcus): align suite with refactored poll/stream"
```

---

## Self-Review Notes

- **Spec coverage:** try/finally impersonation (Task 2), surfaced errors + guarded JSON (Tasks 2–4), Ctrl-C (Task 5), paged polling + backoff (Task 4), Rich Live streaming (Task 5), tests throughout (Tasks 1–6).
- **Type consistency:** `MarcusError`, `_post_to_planner(message)->dict`, `_poll_messages(conversation_id, after_key, *, max_wait, sleep, error_threshold)->generator`, `_render`/Live usage are referenced consistently across tasks.
- **Risk noted in spec:** if `by_key_prefix` later gains server-side after-key paging, `_poll_messages` is the single place to adopt it. Rich `Live` must coexist with the prompt_toolkit session; if it fights the prompt during manual smoke (Task 5 Step 6), fall back to incremental `console.print` while keeping the backoff/error-surfacing logic.
