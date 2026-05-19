# Guard CLI Module System

**Date:** 2026-05-19
**Linear:** 10T-277
**Author:** AJ Hammond
**Origin:** Carter Ross suggestion — Metasploit-style module management for the Guard CLI

## Problem

The Guard CLI already supports installing and running 17 security tools locally (`guard run install`, `guard run tool`), but:

1. **Tool definitions are hardcoded** in `runners/local.py` (`INSTALLABLE_TOOLS`) and `handlers/run.py` (`TOOL_ALIASES`, `FRIENDLY_NAMES`). Adding a tool requires a CLI release.
2. **No discovery UX.** Users can't search, filter, or inspect tools the way Metasploit lets you browse modules. `guard run list` exists but is flat and sparse.
3. **No version tracking or updates.** Users can install but not check versions, update individual tools, or see changelogs.
4. **Claude integration is ad-hoc.** Claude skills have no structured way to discover available tools, check install status, or invoke them. The chariot-mcp server exists but has no module management tools.

## Goals

- New tools can be added by editing a registry file — no CLI release required.
- Users get msf-style `search`, `info`, `options`, `update` commands in both CLI and console.
- Claude (via MCP or structured CLI output) can list, install, and run any module programmatically.
- Backward compatible: `guard run install/tool` continues to work.

## Non-Goals

- Complex dependency management between tools.
- Module categories as a deep hierarchy (msf's exploit/auxiliary/post tree).
- Automatic execution on install (no post-install hooks).
- Workspaces or per-engagement module configs (future iteration).

## Design

### 1. Registry File

A single `modules/registry.json` in the praetorian-cli repo serves as the source of truth for all installable tools. The CLI fetches and caches it locally.

**Schema:**

```json
{
  "version": 1,
  "modules": {
    "brutus": {
      "repo": "praetorian-inc/brutus",
      "description": "Credential attacks across 20+ protocols (SSH, RDP, FTP, SMB, etc.)",
      "category": "credential",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {
        "protocol": {"type": "string", "description": "Target protocol", "required": false},
        "usernames": {"type": "string", "description": "Username file or comma-separated list", "required": false},
        "passwords": {"type": "string", "description": "Password file or comma-separated list", "required": false}
      },
      "args_template": ["--target", "{target}"],
      "tags": ["brute-force", "password", "network"]
    }
  }
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `repo` | yes | GitHub `owner/repo` for release downloads |
| `description` | yes | One-line description |
| `category` | yes | One of: `scanner`, `credential`, `recon`, `cloud`, `cicd`, `ai`, `supply-chain`, `api` |
| `author` | yes | Tool author/team |
| `target_type` | yes | Guard entity type the tool targets (`asset`, `port`, `webpage`, `repository`, etc.) |
| `options` | no | Configurable parameters with type/description/required |
| `args_template` | no | Default argument pattern for local execution. `{target}` is replaced at runtime. |
| `tags` | no | Searchable keywords |
| `binary_pattern` | no | Override for GitHub release asset pattern (default: `{name}-{os}-{arch}*`) |
| `post_install_message` | no | Shown after successful install (e.g., "Requires API key in BRUTUS_TOKEN") |

**Registry lifecycle:**

1. CLI checks `~/.praetorian/registry.json` on module commands.
2. If missing or stale (>24h), fetches from GitHub raw URL: `https://raw.githubusercontent.com/praetorian-inc/praetorian-cli/main/modules/registry.json`.
3. Falls back to bundled copy (shipped with CLI package) if fetch fails.
4. `guard module update --registry` forces a refresh.

### 2. Module Commands (CLI)

New `guard module` subcommand group. Existing `guard run install/installed` continue to work as aliases.

```
guard module search [query]        # Search modules by name, category, tag, description
guard module info <name>           # Full module details: description, options, version, install status
guard module options <name>        # Show configurable options for a module
guard module install <name|all>    # Install module binary from GitHub releases
guard module uninstall <name>      # Remove installed binary
guard module update [name|all]     # Update installed modules to latest release
guard module installed             # List installed modules with versions
guard module list                  # List all available modules (alias for search with no query)
```

All commands support `--json` for structured output.

**`guard module search` examples:**

```
$ guard module search credential
NAME        CATEGORY    INSTALLED   DESCRIPTION
brutus      credential  v1.2.3      Credential attacks across 20+ protocols
nero        credential  —           Default credential scanner

$ guard module search --category scanner --json
[{"name": "nuclei", "category": "scanner", "installed": true, "version": "3.1.0", ...}]
```

**`guard module info` example:**

```
$ guard module info brutus

  Name:        brutus
  Category:    credential
  Author:      Praetorian
  Repository:  praetorian-inc/brutus
  Installed:   v1.2.3 (~/.praetorian/bin/brutus)
  Target:      asset (host:port)
  Description: Credential attacks across 20+ protocols (SSH, RDP, FTP, SMB, etc.)
  Tags:        brute-force, password, network

  Options:
    --protocol    string   Target protocol (auto-detected from port)
    --usernames   string   Username file or comma-separated list
    --passwords   string   Password file or comma-separated list

  Usage:
    guard run tool brutus 10.0.1.5:22
    guard run tool brutus 10.0.1.5:22 --protocol ssh -U users.txt
```

**`guard module update` behavior:**

1. Fetches latest GitHub release tag for the tool's repo.
2. Compares against installed version (stored in `~/.praetorian/versions.json`).
3. If newer, downloads and replaces. Shows before/after versions.

### 3. Console Commands

The interactive console (`guard console`) gets matching commands:

| Console Command | Behavior |
|----------------|----------|
| `search [query]` | Search modules (replaces current capabilities-only search) |
| `info <name>` | Show module details panel |
| `options [name]` | Show options for active or named module |
| `update [name\|all]` | Update installed modules |
| `install <name\|all>` | Install module (existing, unchanged) |
| `installed` | List installed (existing, unchanged) |

`search` in the console merges module registry results with backend capabilities so users see the full picture.

### 4. Version Tracking

Install and update operations write to `~/.praetorian/versions.json`:

```json
{
  "brutus": {"version": "v1.2.3", "installed_at": "2026-05-19T12:00:00Z", "path": "~/.praetorian/bin/brutus"},
  "nuclei": {"version": "v3.1.0", "installed_at": "2026-05-18T09:30:00Z", "path": "~/.praetorian/bin/nuclei"}
}
```

Version is extracted from the GitHub release tag at install time via `gh release view --repo <repo> --json tagName`.

### 5. Claude Integration

#### Structured CLI Output

All `guard module` commands support `--json`. This is sufficient for Claude Code skills that shell out to the CLI.

Example Claude skill flow:
```
1. guard module search --json              → discover available tools
2. guard module info brutus --json         → check options and install status
3. guard module install brutus --json      → install if needed
4. guard run tool brutus 10.0.1.5:22 --json → execute and get structured results
```

#### MCP Tools

Add to the existing `chariot-mcp` server (or a new lightweight `guard-mcp` that wraps the CLI):

| MCP Tool | Description |
|----------|-------------|
| `list_modules` | List all modules with install status. Params: `category`, `query` (optional filters) |
| `module_info` | Get full details for a module. Params: `name` (required) |
| `install_module` | Install a module. Params: `name` (required), `force` (optional) |
| `run_module` | Execute a module against a target. Params: `name`, `target` (required), `options` (optional dict) |

MCP tools internally call the same Python functions as the CLI, not subprocess.

### 6. Tool Plugin Migration

The existing `ToolPlugin` classes in `runners/local.py` (BrutusPlugin, NucleiPlugin, etc.) remain for now — they handle argument building nuances that can't be captured in a simple `args_template`.

Migration path:
1. Registry `args_template` handles simple tools (most of them).
2. Custom plugins override `args_template` when needed (Brutus protocol detection, etc.).
3. Plugin code stays in `runners/local.py` but is loaded dynamically by name from the registry rather than a hardcoded dict.

The `TOOL_PLUGINS` dict becomes auto-built: registry entry has plugin? Use it. Has `args_template`? Generate a plugin. Neither? Use default passthrough.

### 7. Backward Compatibility

| Old Command | New Canonical | Behavior |
|-------------|---------------|----------|
| `guard run install <name>` | `guard module install <name>` | Alias, both work |
| `guard run installed` | `guard module installed` | Alias, both work |
| `guard run list` | `guard module list` | Alias, both work |
| `guard run tool <name> <target>` | `guard run tool <name> <target>` | Unchanged |
| Console `install`, `installed` | Console `install`, `installed` | Unchanged |

`INSTALLABLE_TOOLS` and `TOOL_ALIASES` dicts are replaced by functions that read from the cached registry. Import sites that reference these dicts get the same interface (dict-like access) via a lazy-loading wrapper.

## File Changes

| File | Change |
|------|--------|
| `modules/registry.json` | **New.** Module registry manifest. |
| `praetorian_cli/registry.py` | **New.** Registry loader: fetch, cache, parse, lazy dict interface. |
| `praetorian_cli/handlers/module.py` | **New.** `guard module` CLI subcommand group. |
| `praetorian_cli/ui/console/commands/tools.py` | **Modified.** Add `search`, `info`, `options`, `update` console commands. Wire to registry. |
| `praetorian_cli/runners/local.py` | **Modified.** `INSTALLABLE_TOOLS` becomes `get_installable_tools()` reading from registry. Version tracking on install. |
| `praetorian_cli/handlers/run.py` | **Modified.** `TOOL_ALIASES`/`FRIENDLY_NAMES` read from registry. `install`/`installed` become aliases to `module` commands. |
| `praetorian_cli/handlers/chariot.py` | **Modified.** Register `module` subcommand group. |

## Testing

- Unit tests for registry parsing, caching, and staleness logic.
- Unit tests for `search` filtering (name, category, tag, description substring).
- Integration test: `guard module install` + `guard module installed` + `guard module info` round-trip.
- Console tests: `search`, `info`, `options` render correctly.
- Backward compat: existing `guard run install`/`guard run list` still work.
- Offline: CLI works with bundled registry when network fetch fails.
