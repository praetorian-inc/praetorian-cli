# Guard CLI Improvements — Design Spec

**Date:** 2026-03-24
**Author:** AJ Hammond
**Status:** Approved

## Problem

Engineers using the Guard CLI for engagements face several gaps compared to the GUI:

1. **Search is prefix-only** — no contains/fulltext, no cross-type searching. Backend supports it via Neo4j graph queries but CLI only uses DynamoDB prefix matching. Backend timeouts on large datasets need mitigation.
2. **No reporting automation** — no CLI command for report generation or export. Only `add risk` and webhook exist.
3. **Evidence is scattered** — depending on which capability created a risk, evidence lives in different places (attributes, webpages, files, inline). No single command retrieves it all.
4. **Marcus integration is basic** — the Textual TUI exists but lacks engagement context, tool call visibility, `@agent` support, and inline one-shot queries.
5. **No operator console experience** — CLI is CRUD-oriented (`guard verb noun`), not workflow-oriented like Metasploit. Engineers need a stateful, context-aware interactive session.

## Decisions

- **Both standalone commands AND interactive console** — standalone for scripting/automation, console for the premium operator experience.
- **Account + scope context model** — `set account` for engagement impersonation, `set scope` for domain/asset group filtering. Two layers, no deeper nesting.
- **Hybrid Marcus** — inline `ask` for quick queries, dedicated `marcus` mode for multi-turn conversation. Both share conversation state and respect engagement context.
- **Dual search** — keep fast `search` (DynamoDB prefix), add `find` (Neo4j fulltext/contains). Clean separation with clear performance expectations.
- **Evidence hydration in SDK + report generation via backend API** — `get risk --evidence` chases all evidence sources, `report generate` calls backend's report API.

## Design

### 1. Fulltext Search: `find` Command

**New files:**
- `handlers/find.py` — CLI handler
- SDK uses existing `search.by_query()` with `Node.search` field

**Interface:**
```
guard find "example.com"                          # cross-type fulltext
guard find "CVE-2024" --type risk                 # scoped to risks
guard find "ssh" --type asset --contains name     # contains on specific field
guard find "10.0.1" --type asset --limit 50       # with result limit
guard find "admin" --type risk --format json       # machine-readable output
```

**Behavior:**
- Uses Neo4j graph queries via `search.by_query()` with `Node.search` for fulltext
- Cross-type by default — searches assets, risks, attributes, technologies in one query
- Defaults to `limit=100` to mitigate backend timeout on large record sets
- Shows warning when result count hits limit: "Showing 100 of potentially more results. Use --limit to increase."
- Rich table output with type column, key, name/dns, status
- `--format json` for scripting

**Key difference from `search`:**
- `search` = fast, prefix-only, DynamoDB, existing workflows preserved
- `find` = powerful, fulltext/contains, Neo4j, clear performance expectations

### 2. Evidence Hydration & Reporting

#### 2a. `get risk --evidence`

**New SDK method:** `risks.hydrate_evidence(key)` in `sdk/entities/risks.py`

Chases evidence from all locations:
1. Risk record itself — `content` field, inline findings
2. Attributes — via `search.by_source(risk_key, kind='attribute')`
3. Referenced webpages — via `search.by_source(risk_key, kind='webpage')`, then fetch content
4. Files — evidence files in S3 under risk key path via `files.get()`
5. Definition — risk definition markdown (description, impact, recommendation, references)

Returns normalized structure:
```python
{
    "risk": { ... },                    # full risk record
    "definition": {                     # parsed definition markdown
        "description": "...",
        "impact": "...",
        "recommendation": "...",
        "references": ["..."]
    },
    "evidence": [
        {"source": "attribute", "name": "affected_versions", "value": "1.0-1.4"},
        {"source": "webpage", "url": "https://...", "status": 200, "content": "..."},
        {"source": "file", "path": "evidence/...", "size": 2400}
    ]
}
```

**CLI output:** Renders sections — Description, Evidence (grouped by source type), Impact, Recommendation, References. `--format json` for scripting.

**Enhanced `handlers/get.py`:** Add `--evidence` flag to `get risk` subcommand.

#### 2b. Report Generation

**New file:** `handlers/report.py`

```
guard report generate                                  # interactive prompts
guard report generate --title "Q1 Pentest" --client "Acme Corp"
guard report generate --risks "status:OH" --group-by-phase
guard report generate --format pdf --output ./report.pdf
guard report validate                                  # pre-check requirements
```

- `report generate` calls `POST /export/report` with configuration
- `report validate` calls `POST /validate-report` — lists missing definitions, narratives, phase tags before generation
- Validation failures show actionable fix steps per item

### 3. Interactive Console: `guard console`

**New module:** `ui/console/`

```
ui/console/
├── __init__.py          # run_console() entry point
├── console.py           # GuardConsole class (follows Aegis menu pattern)
├── completer.py         # ConsoleCompleter with fuzzy matching + tab completion
├── context.py           # EngagementContext dataclass
├── commands.py          # Command dispatch and registration
├── renderer.py          # Rich-based output (tables, panels, markdown, spinners)
└── theme.py             # Shared with Aegis theme (ui/aegis/theme.py)
```

**Framework:** Rich (not Textual) — matches Aegis menu pattern, better for command-driven interaction. Uses `prompt_toolkit` for input (available via Click dependency).

#### 3a. Engagement Context

```python
@dataclass
class EngagementContext:
    account: Optional[str] = None       # SDK impersonation
    scope: Optional[str] = None         # domain/asset group filter
    conversation_id: Optional[str] = None  # shared ask/marcus state
    mode: str = "agent"                 # query or agent
    active_agent: Optional[str] = None  # @aurelius, etc.
```

**Commands:**
```
set account client@example.com
set scope *.example.com
unset scope
show context
switch <account>                        # quick switch with tab-completion
```

Account sets SDK impersonation header. Scope applies console-layer filtering to search/find/list/ask.

#### 3b. Console Commands

**Context:** `set`, `unset`, `show`, `switch`

**Recon & Search:**
- `search <term>` — fast prefix (DynamoDB)
- `find <term>` — fulltext graph (Neo4j)
- `assets` / `risks` / `jobs` — aliases for list with scope filter
- `info <key>` — auto-detects asset/risk by key prefix, shows details

**Operations:**
- `scan <asset> [capability]` — alias for `add job`
- `add risk <asset> <name>` — quick risk creation
- `tag <risk_key> <tag>` — quick tagging

**Evidence & Reporting:**
- `evidence <risk_key>` — alias for `get risk --evidence`
- `report generate` / `report validate`

**Marcus:**
- `ask "question"` — inline one-shot
- `marcus` — multi-turn conversation mode
- Both detailed in Section 4

**Aegis:** `aegis` — drops into existing Aegis menu, returns on exit

**Utility:** `help`, `history`, `clear`, `quit`

#### 3c. Scope Filtering

Applied at console layer, not SDK:
- `search`/`find`: adds dns filter or wraps in scope-aware query
- `list assets`/`risks`: passes scope as `--filter`
- `ask`/`marcus`: prepends context to message sent to `/planner`

#### 3d. Console Entry Point

**New handler addition to `handlers/agent.py` or new `handlers/console.py`:**
```
guard console
guard console --account client@example.com
```

### 4. Marcus Integration (Inline & Conversation)

#### 4a. Inline `ask`

```
guard > ask "what assets have port 22 open?"
⠋ Querying...
┌─ Marcus ─────────────────────────────────────┐
│ Found 14 assets with port 22 open: ...       │
└──────────────────────────────────────────────┘
guard >
```

**Flow:**
1. POST `/planner` with `{"message": context_prefix + user_message, "mode": mode}`
2. Poll `#message#{conversation_id}#` every 1s (tighter than TUI's 3s for snappy inline feel)
3. Tool calls shown as compact spinner lines: `⠋ Executing query...` → `✓ Found 14 results`
4. Final `chariot` role message rendered as Rich panel with markdown
5. Conversation ID stored in context for follow-up `ask` commands

```
guard > ask "which of those have critical risks?"    # continues conversation
guard > ask --new "unrelated question"                # fresh conversation
```

**Standalone command (outside console):**
```
guard ask "summarize critical risks" --account client@example.com
guard ask "summarize critical risks" --format json | jq .
```

#### 4b. Dedicated `marcus` Mode

```
guard > marcus
marcus > analyze the top 5 risks by severity
⠋ Querying risks... ✓ Analyzing 5 results...
[Rich markdown response]

marcus > @aurelius scan cloud infrastructure
⠋ Delegating to aurelius... ✓ Job queued

marcus > back
guard >
```

**Behavior:**
- Defaults to `agent` mode. `marcus --query` starts in query mode.
- `@agent_name` switches active agent (matches GUI behavior)
- Tool calls rendered inline with spinner + completion
- Job status transitions polled and shown (JQ→JR→JP/JF)
- `back` returns to console, conversation stays alive
- `marcus --new` starts fresh conversation

#### 4c. Engagement Context Injection

```python
if context.scope:
    message = f"Focus on assets matching {context.scope}. {user_message}"
# account impersonation handled by SDK header, no message prefix needed
```

#### 4d. Shared State

Both `ask` and `marcus` share `context.conversation_id`, `context.mode`, and `context.active_agent`. Switching accounts clears conversation state.

### 5. Integration Summary

#### Standalone commands (work outside console)

| Command | Type | Description |
|---------|------|-------------|
| `guard find <term>` | New | Fulltext graph search across types |
| `guard get risk <key> --evidence` | Enhanced | Hydrated evidence from all sources |
| `guard report generate` | New | Formal report via backend API |
| `guard report validate` | New | Pre-check report requirements |
| `guard ask "<message>"` | New | One-shot Marcus query (non-interactive) |
| `guard console` | New | Interactive operator console |

#### Unchanged

- All existing `guard add/get/list/update/delete/search` commands
- Aegis menu (`guard aegis`)
- MCP server (`guard agent mcp`) — benefits from new SDK methods automatically
- SDK API surface — additions only, no breaking changes

#### Error handling

- Console catches all exceptions, renders as Rich error panels, never crashes
- Scope mismatches show hint: "No results. Current scope: *.example.com — use 'unset scope' to broaden"
- Marcus API errors show error and offer retry
- Report validation failures list each missing item with actionable fix steps

#### Testing

- SDK methods — unit tests with mocked API responses (existing `sdk/test/` patterns)
- Console commands — integration tests via existing test harness
- Marcus — extend `test_conversation.py` with inline `ask` tests

## Implementation Order

1. `find` command + SDK fulltext search method
2. `risks.hydrate_evidence()` SDK method + `get risk --evidence`
3. `report generate` / `report validate` handlers
4. Standalone `guard ask` command
5. Console module (`ui/console/`) with context, commands, renderer
6. Marcus integration in console (inline `ask` + dedicated `marcus` mode)
7. Console-specific aliases and scope filtering
