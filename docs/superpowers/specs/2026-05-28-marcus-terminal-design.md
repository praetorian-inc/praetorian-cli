# Marcus Terminal — Correctness, Performance, Streaming UX

**Date:** 2026-05-28
**Branch:** `fix/marcus-terminal` (new, off `main`)
**Status:** Design — pending implementation plan

## Problem

The Marcus AI console mode (`praetorian_cli/ui/console/commands/marcus.py`) POSTs
to `/planner`, then **polls** `#message#<conversation_id>#` keys to stream tool
calls and the final response. Review for "optimize + ensure no errors" surfaced
correctness bugs, an inefficient poll loop, and a fragile rendering path.

## Goals

Harden and streamline the Marcus terminal across four dimensions (and anything
else found during implementation):

1. **Correctness / no errors**
2. **Poll-loop performance**
3. **Streaming UX**
4. **Test coverage**

## Findings → Fixes

### 1. Correctness

- **Impersonation not restored on error** (`marcus.py:122-133`):
  `self.sdk.keychain.account` is cleared then restored *without* `try/finally`.
  If `chariot_request` raises in between, impersonation stays disabled for the
  rest of the session. → Wrap in `try/finally`; restore unconditionally.
- **Silent `except Exception: pass`** (`151-152`, `223-224`): genuine API/parse
  errors are swallowed, so failures look like hangs/timeouts. → Catch narrowly,
  log/surface transient errors, and distinguish "still working" from "errored".
- **`response.json()` unguarded** (`139`): a non-JSON error body throws. → Guard
  with a clear error message including status code + body snippet.
- **Ctrl-C mid-response** (`164-226`): not caught inside `_send_to_marcus`; only
  the outer conversation loop handles it → traceback while "Thinking…". → Catch
  `KeyboardInterrupt`, cancel cleanly, return to the prompt.

### 2. Performance

- **Full-conversation refetch every 1s** (`164-226`): `by_key_prefix` pulls the
  entire conversation each second for up to 180s, filtered client-side by
  `> last_key` — O(messages × polls). → Page by after/offset key if the search
  API supports it; otherwise request only the tail. Add idle backoff (e.g.
  1s → 2s → 3s, capped) that resets on new activity.

### 3. Streaming UX

- **Final-only render**: assistant text appears only at the end. → Use a Rich
  `Live` region to render tool activity and incremental assistant text as they
  arrive.
- **`\r` line-rewrite hack** (`215`) for retroactive tool-name fixes is fragile
  across terminal widths. → Replace with the `Live` region; prefer structured
  tool-name fields over heuristic inference where the API provides them.

### 4. Tests

- New `test_console_marcus.py` covering:
  - Tool-name parsing (`_parse_tool_name`) and result summary (`_parse_tool_result`)
    across structured and unstructured payloads.
  - Impersonation restore on both success and exception (the `try/finally` fix).
  - Poll-loop termination on `chariot` message, timeout, and Ctrl-C.
  - `response.json()` failure path.
  - 403 retry-as-Praetorian routing.

## Approach

Refactor `_send_to_marcus` into focused, testable units:

- `_post_to_planner(message)` — POST, handle 403 retry-as-Praetorian inside a
  `try/finally` impersonation guard, guarded JSON parse.
- `_poll_messages(conversation_id, after_key)` — paged fetch + backoff, yields
  new messages; raises/annotates real errors instead of swallowing them.
- `_render_stream(messages)` — Rich `Live` region rendering tool activity and
  incremental text.

Keep the public command surface (`ask`, `marcus`, `marcus read/ingest/do`,
`research`/`critfinder`) unchanged.

## Non-Goals

- Changing the `/planner` backend contract.
- Replacing polling with websockets/SSE (out of scope unless the API already
  supports it; revisit separately).

## Risks

- The search API may not support after-key paging; if so, the tail-fetch
  optimization degrades to "fetch all" but the correctness + UX fixes still land.
- Rich `Live` inside the prompt-toolkit session must not fight the prompt; verify
  interaction and fall back to incremental `print` if needed.
