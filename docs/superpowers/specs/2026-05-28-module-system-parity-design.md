# Module System — Live-API Parity + Metasploit-grade UX

**Date:** 2026-05-28
**Branch:** `feat/module-system` (PR #226)
**Linear:** 10T-277 (follow-up)
**Status:** Design — pending implementation plan

## Problem

The CLI ships a hand-curated `modules/registry.json` of 17 Roman-emperor-named
tools. Guard's backend defines **63 capabilities** canonically
(`backend/pkg/tasks/loader.go` + `pkg/compute/registries/agora.go`), with a
richer schema (`AgoraCapability`). The two have drifted:

- **Match (9):** brutus, nuclei, trajan, julius, augustus, hadrian, vespasian,
  constantine, caligula.
- **In CLI but not a guard capability (8):** titus, nerva, gato, cato, florian,
  aurelian, nero, pius (guard has `pius_discovery`).
- **Schema mismatch:** CLI stores `{repo, options{type,description,required}}`;
  guard exposes `AgoraCapability` (Title, Target[], Category, Surface, RunsOn,
  Version, Executor, Integration, Parameters[]).

Hand-maintaining the registry guarantees ongoing drift. The CLI should reflect
what guard actually offers, and the module UX should be as polished and
streamlined ("Metasploit-grade") as possible.

## Goals

1. **1:1 parity with guard** for capability metadata — guard's backend is the
   single source of truth.
2. **Streamlined discovery/install/run UX** across CLI, interactive console, and
   MCP, all backed by one catalog and one renderer.
3. **Backward compatibility** — existing `guard run install/tool/list/installed`
   keep working.
4. **Graceful offline behavior** — module metadata commands answer even with no
   network / no auth.

## Non-Goals (YAGNI)

- Inter-tool dependency resolution.
- Per-engagement module profiles / workspaces.
- GPG signing of binaries (SHA-256 checksum only).
- Auto-run on install.

## Architecture

### Data sources — three-layer resolution

```
live API (sdk.capabilities.list)
   → ~/.praetorian/capabilities-cache.json  (TTL, e.g. 24h)
   → bundled snapshot shipped with the CLI
```

**`CapabilityCatalog`** (new, replaces the metadata role of `registry.py`):

- `refresh(force=False) -> bool` — fetch all capabilities via
  `sdk.capabilities.list()`, normalize the `AgoraCapability` shape, write the
  cache atomically (reuse the atomic-write pattern already in `registry.py`).
- `all() -> list[Capability]` — resolve from cache; refresh if stale; fall back
  to bundled snapshot when API + cache are both unavailable.
- `get(name) -> Capability | None` — case-insensitive lookup.
- `search(query, *, category, surface, target, tag, installed) -> list` —
  fuzzy + ranked matching with filters (see UX below).
- Normalized `Capability` fields mirror guard: `name`, `title`, `target` (list),
  `description`, `category`, `surface`, `runs_on`, `version`, `executor`,
  `integration`, `parameters` (each: `name`, `description`, `type`, `default`,
  `required`, `options`/enum).

Offline detection: a failed/!ok API call or missing auth → use cache, then
bundled snapshot, and annotate the result source (`live` / `cached (age)` /
`bundled`) so commands can warn the user (to stderr; never pollutes `--json`).

### Install source — slim install-manifest

The API carries no repo/binary field, so install source stays local.
`modules/registry.json` shrinks to a pure **install-manifest**:

```json
{
  "version": 2,
  "modules": {
    "brutus":   { "repo": "praetorian-inc/brutus",   "binary_pattern": "brutus-{os}-{arch}*",   "plugin": "brutus" },
    "pius":     { "repo": "praetorian-inc/pius", "capability": "pius_discovery", "local_only": false },
    "titus":    { "repo": "praetorian-inc/titus",     "local_only": true },
    "nerva":    { "repo": "praetorian-inc/nerva",     "local_only": true }
  }
}
```

- `repo` / `binary_pattern` / `plugin` — install + arg-building info only.
- `capability` (optional) — maps an install name to its guard capability when
  they differ (`pius` → `pius_discovery`).
- `local_only: true` — tools with no guard capability (titus, nerva, gato, cato,
  florian, aurelian, nero, and pius if it has no capability). Each is verified
  against guard before tagging; listings mark them `[local-only]`.

### Merge model

Listings = **union** of (a) live guard capabilities and (b) install-manifest
entries, keyed by name (via `capability` alias where present). Each row carries:
metadata source (guard vs local-only), install status + version (from
`~/.praetorian/versions.json`), and installability (has a manifest entry).

## CLI / Console commands

Both surfaces call the same `CapabilityCatalog` and a shared renderer so output
is identical.

| Command | Behavior |
|---|---|
| `search [query]` | Fuzzy + ranked, typo-tolerant. Filters: `--category --surface --target --tag --installed`. Numbered results referencable by `#`. |
| `info <name\|#>` | Rich panel: title, version, surface, target types, executor, full parameter table (type/default/required/enum) from live API. Accepts a result number from the last search. |
| `options <name>` | Parameter table only. |
| `list` | All capabilities (search with empty query). |
| `installed` | Locally installed binaries + versions. |
| `install <name\|all> [--force]` | Rich progress bars; **parallel** for `all`; optional **SHA-256** verification of the downloaded asset; post-install summary. |
| `uninstall <name>` | Remove binary + version record (`registry.remove_version`). |
| `update [name\|all]` | Compare installed vs latest release tag; reinstall if newer; show `old → new`. |
| `sync` | Force-refresh the capability catalog from the API; report staleness. |

- `--json` on every command; notices/progress to stderr so JSON stays clean.
- Fuzzy ranking: exact name > prefix > substring > fuzzy (bounded edit distance),
  tie-broken by name. Pure-Python, no new heavy dependency.

## Metasploit interactive flow (console)

Polish the existing `use`/`set`/`options`/`run`/`back` (`console.py:192-199`,
selected-tool mode at `:263`):

- `use <module|#>` enters module context; prompt shows `guard (brutus) >`.
- `options` / `show options` auto-populated from **live API parameters** —
  required flagged, defaults shown, enum hints listed.
- `set <param> <value>` / `unset` — validated against the parameter's type/enum.
- `run` / `exploit` — execute with set options; local if installed, else remote.
- **Tab-completion** extended to subcommands and live module names (currently
  only top-level verbs complete via the hardcoded `CONSOLE_COMMANDS`).

## MCP parity

`list_modules` / `module_info` resolve through `CapabilityCatalog`, so Claude
sees all guard capabilities (not 17). `install_module` / `run_module` keep their
current contract.

## Error handling

- API/network failures degrade to cache → bundled snapshot with a clear source
  annotation, never an opaque crash.
- Install failures (missing `gh`, no matching asset, checksum mismatch) produce
  specific, actionable messages; `install all` reports per-tool status and never
  aborts the batch on one failure.

## Testing

- `CapabilityCatalog`: live/cache/bundled resolution, staleness, normalization,
  fuzzy ranking, filters. Mock `sdk.capabilities.list`.
- Install-manifest: merge with live caps, `local_only` tagging, `capability`
  aliasing (`pius` → `pius_discovery`).
- CLI commands: `--json` shape, numbered-result resolution, parallel install
  status aggregation, SHA-256 mismatch path.
- Console: module subcommand dispatch, `use/set/options/run` with API params,
  tab-completion sources.
- Backward compat: `guard run list/installed/tool` unchanged.

## Migration / compatibility

- `registry.py` keeps `record_version/get_version/remove_version` and the
  install-manifest loader; its metadata responsibilities move to
  `CapabilityCatalog`. `INSTALLABLE_TOOLS` / `TOOL_ALIASES` now derive from the
  manifest + catalog.
- Bump `registry.json` `version` to 2; ship a bundled capability snapshot.
