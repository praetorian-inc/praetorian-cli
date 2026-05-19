# Guard CLI Module System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded tool definitions in the Guard CLI with a dynamic registry file, add msf-style `search`/`info`/`options`/`update` commands, version tracking, and MCP tools for Claude integration.

**Architecture:** A JSON registry file (`modules/registry.json`) becomes the single source of truth for tool metadata. A new `registry.py` module handles fetching, caching (at `~/.praetorian/registry.json`), and serving this data through a dict-like interface. Existing `INSTALLABLE_TOOLS` and `TOOL_ALIASES` are replaced by functions reading from this registry. New `guard module` CLI commands and console commands expose search/info/update UX, all with `--json` support. MCP tools wrap the same Python functions.

**Tech Stack:** Python 3.10+, Click 8.x (CLI framework), Rich (console rendering), prompt_toolkit (interactive console), mcp 1.12+ (MCP server)

**Repo:** `praetorian-inc/praetorian-cli` at `/Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli/`
**Branch:** `feat/module-system`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `modules/registry.json` | **New.** Source-of-truth module manifest. All 17 existing tools + metadata. |
| `praetorian_cli/registry.py` | **New.** Fetch, cache, parse registry. Lazy dict interface replacing `INSTALLABLE_TOOLS`. Version tracking read/write. |
| `praetorian_cli/handlers/module.py` | **New.** `guard module` Click subcommand group: search, info, options, install, uninstall, update, installed, list. |
| `praetorian_cli/runners/local.py` | **Modified.** Remove hardcoded `INSTALLABLE_TOOLS` dict, replace with `get_installable_tools()` from registry. Add version recording on install. |
| `praetorian_cli/handlers/run.py` | **Modified.** `TOOL_ALIASES`/`FRIENDLY_NAMES` read from registry. |
| `praetorian_cli/main.py` | **Modified.** Import and register `module` handler. |
| `praetorian_cli/ui/console/commands/tools.py` | **Modified.** Wire `search`, `info`, `update` console commands to registry. |
| `praetorian_cli/ui/console/console.py` | **Modified.** Add `update`, `module` to `CONSOLE_COMMANDS` list and dispatch table. |
| `praetorian_cli/sdk/mcp_server.py` | **Modified.** Add explicit module management MCP tools. |
| `MANIFEST.in` | **Modified.** Include `modules/registry.json` in package. |
| `praetorian_cli/sdk/test/test_registry.py` | **New.** Unit tests for registry module. |
| `praetorian_cli/sdk/test/test_module_cli.py` | **New.** Unit tests for `guard module` CLI commands. |
| `praetorian_cli/sdk/test/ui/test_console_modules.py` | **New.** Unit tests for console module commands. |

---

### Task 1: Create the Registry JSON File

**Files:**
- Create: `modules/registry.json`

This is the source-of-truth manifest. Seed it with all 17 tools currently hardcoded in `runners/local.py` `INSTALLABLE_TOOLS` and the agent metadata from `handlers/run.py` `FRIENDLY_NAMES`.

- [ ] **Step 1: Create registry.json with all existing tools**

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
        "protocol": {"type": "string", "description": "Target protocol (auto-detected from port)", "required": false},
        "usernames": {"type": "string", "description": "Username file or comma-separated list", "required": false},
        "passwords": {"type": "string", "description": "Password file or comma-separated list", "required": false}
      },
      "args_template": ["--target", "{target}"],
      "tags": ["brute-force", "password", "network"]
    },
    "julius": {
      "repo": "praetorian-inc/julius",
      "description": "LLM/AI service fingerprinting",
      "category": "ai",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["-t", "{target}"],
      "tags": ["llm", "ai", "fingerprint"]
    },
    "augustus": {
      "repo": "praetorian-inc/augustus",
      "description": "LLM jailbreak & prompt injection attacks (190+ probes)",
      "category": "ai",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "-t", "{target}"],
      "tags": ["llm", "ai", "jailbreak", "injection"]
    },
    "titus": {
      "repo": "praetorian-inc/titus",
      "description": "Secret scanning & credential leak detection (487 rules)",
      "category": "scanner",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {
        "validation": {"type": "string", "description": "Enable secret validation (true/false)", "required": false}
      },
      "args_template": ["scan", "{target}"],
      "tags": ["secrets", "credentials", "leak"]
    },
    "trajan": {
      "repo": "praetorian-inc/trajan",
      "description": "CI/CD pipeline security scanning",
      "category": "cicd",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {
        "token": {"type": "string", "description": "GitHub/GitLab token for API access", "required": false}
      },
      "args_template": ["scan", "{target}"],
      "tags": ["cicd", "pipeline", "github", "gitlab"]
    },
    "cato": {
      "repo": "praetorian-inc/cato",
      "description": "Injection scanner (SQLi, SSRF, SSTI, XXE)",
      "category": "scanner",
      "author": "Praetorian",
      "target_type": "webpage",
      "options": {},
      "args_template": ["scan", "-u", "{target}"],
      "tags": ["injection", "sqli", "ssrf", "ssti", "xxe"]
    },
    "nerva": {
      "repo": "praetorian-inc/nerva",
      "description": "Service fingerprinting (120+ protocols)",
      "category": "recon",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["-t", "{target}"],
      "tags": ["fingerprint", "service", "protocol"]
    },
    "vespasian": {
      "repo": "praetorian-inc/vespasian",
      "description": "API discovery from traffic",
      "category": "api",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "{target}"],
      "tags": ["api", "discovery", "traffic"]
    },
    "nuclei": {
      "repo": "praetorian-inc/nuclei",
      "description": "Vulnerability scanner with template engine",
      "category": "scanner",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {
        "templates": {"type": "string", "description": "Template directory or file", "required": false}
      },
      "args_template": ["-u", "{target}", "-jsonl"],
      "tags": ["vulnerability", "templates", "cve"]
    },
    "gato": {
      "repo": "praetorian-inc/gato",
      "description": "GitHub Actions pipeline scanner",
      "category": "cicd",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {
        "token": {"type": "string", "description": "GitHub token", "required": false}
      },
      "args_template": ["enumerate", "-t", "{target}"],
      "tags": ["github", "actions", "pipeline"]
    },
    "constantine": {
      "repo": "praetorian-inc/constantine",
      "description": "Repository security analysis",
      "category": "scanner",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "{target}"],
      "tags": ["repository", "code", "security"]
    },
    "aurelian": {
      "repo": "praetorian-inc/aurelian",
      "description": "Cloud security reconnaissance (AWS/Azure/GCP)",
      "category": "cloud",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "{target}"],
      "tags": ["cloud", "aws", "azure", "gcp", "recon"]
    },
    "pius": {
      "repo": "praetorian-inc/pius",
      "description": "Organizational asset discovery",
      "category": "recon",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "{target}"],
      "tags": ["discovery", "org", "asset"]
    },
    "florian": {
      "repo": "praetorian-inc/florian",
      "description": "Authentication flow testing",
      "category": "api",
      "author": "Praetorian",
      "target_type": "webpage",
      "options": {},
      "args_template": ["scan", "-u", "{target}"],
      "tags": ["auth", "authentication", "flow"]
    },
    "caligula": {
      "repo": "praetorian-inc/caligula",
      "description": "Supply chain security scanner",
      "category": "supply-chain",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["scan", "{target}"],
      "tags": ["supply-chain", "dependency", "sbom"]
    },
    "hadrian": {
      "repo": "praetorian-inc/hadrian",
      "description": "API security testing",
      "category": "api",
      "author": "Praetorian",
      "target_type": "webpage",
      "options": {},
      "args_template": ["scan", "-u", "{target}"],
      "tags": ["api", "security", "testing"]
    },
    "nero": {
      "repo": "praetorian-inc/nero",
      "description": "Default credential scanner",
      "category": "credential",
      "author": "Praetorian",
      "target_type": "asset",
      "options": {},
      "args_template": ["-t", "{target}"],
      "tags": ["default", "credentials", "scanner"]
    }
  }
}
```

- [ ] **Step 2: Update MANIFEST.in to include registry**

In `MANIFEST.in`, add:
```
include modules/registry.json
```

- [ ] **Step 3: Commit**

```bash
git add modules/registry.json MANIFEST.in
git commit -m "feat(modules): add registry.json manifest with all 17 tools"
```

---

### Task 2: Create the Registry Module (`registry.py`)

**Files:**
- Create: `praetorian_cli/sdk/test/test_registry.py`
- Create: `praetorian_cli/registry.py`

Core module: fetch, cache, parse registry.json. Provides `get_modules()`, `get_module(name)`, `search_modules(query, category)`, and version tracking via `~/.praetorian/versions.json`.

- [ ] **Step 1: Write the failing tests**

Create `praetorian_cli/sdk/test/test_registry.py`:

```python
"""Unit tests for the module registry."""
import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

from praetorian_cli.registry import (
    ModuleRegistry,
    CACHE_PATH,
    VERSIONS_PATH,
    BUNDLED_REGISTRY_PATH,
)


SAMPLE_REGISTRY = {
    "version": 1,
    "modules": {
        "brutus": {
            "repo": "praetorian-inc/brutus",
            "description": "Credential attacks across 20+ protocols",
            "category": "credential",
            "author": "Praetorian",
            "target_type": "asset",
            "options": {
                "protocol": {"type": "string", "description": "Target protocol", "required": False},
            },
            "args_template": ["--target", "{target}"],
            "tags": ["brute-force", "password"],
        },
        "nuclei": {
            "repo": "praetorian-inc/nuclei",
            "description": "Vulnerability scanner with template engine",
            "category": "scanner",
            "author": "Praetorian",
            "target_type": "asset",
            "options": {},
            "args_template": ["-u", "{target}", "-jsonl"],
            "tags": ["vulnerability", "cve"],
        },
        "julius": {
            "repo": "praetorian-inc/julius",
            "description": "LLM/AI service fingerprinting",
            "category": "ai",
            "author": "Praetorian",
            "target_type": "asset",
            "options": {},
            "args_template": ["-t", "{target}"],
            "tags": ["llm", "ai"],
        },
    },
}


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect registry cache and versions to a temp dir."""
    cache = tmp_path / "registry.json"
    versions = tmp_path / "versions.json"
    monkeypatch.setattr("praetorian_cli.registry.CACHE_PATH", str(cache))
    monkeypatch.setattr("praetorian_cli.registry.VERSIONS_PATH", str(versions))
    return tmp_path


@pytest.fixture
def seeded_cache(tmp_home):
    """Write SAMPLE_REGISTRY into the cache file."""
    cache = tmp_home / "registry.json"
    cache.write_text(json.dumps(SAMPLE_REGISTRY))
    return tmp_home


class TestRegistryLoading:
    def test_loads_from_cache(self, seeded_cache):
        reg = ModuleRegistry()
        modules = reg.get_modules()
        assert "brutus" in modules
        assert "nuclei" in modules
        assert modules["brutus"]["category"] == "credential"

    def test_falls_back_to_bundled(self, tmp_home):
        """When cache is missing, loads the bundled registry."""
        reg = ModuleRegistry()
        modules = reg.get_modules()
        assert len(modules) > 0

    def test_get_module_by_name(self, seeded_cache):
        reg = ModuleRegistry()
        mod = reg.get_module("brutus")
        assert mod is not None
        assert mod["repo"] == "praetorian-inc/brutus"

    def test_get_module_unknown_returns_none(self, seeded_cache):
        reg = ModuleRegistry()
        assert reg.get_module("nonexistent") is None

    def test_get_module_case_insensitive(self, seeded_cache):
        reg = ModuleRegistry()
        assert reg.get_module("BRUTUS") is not None
        assert reg.get_module("Brutus") is not None


class TestRegistrySearch:
    def test_search_by_name(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules("brut")
        assert any(r["name"] == "brutus" for r in results)

    def test_search_by_category(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules(category="credential")
        names = [r["name"] for r in results]
        assert "brutus" in names
        assert "nuclei" not in names

    def test_search_by_tag(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules("llm")
        assert any(r["name"] == "julius" for r in results)

    def test_search_by_description(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules("template")
        assert any(r["name"] == "nuclei" for r in results)

    def test_search_no_query_returns_all(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules()
        assert len(results) == 3

    def test_search_combined_query_and_category(self, seeded_cache):
        reg = ModuleRegistry()
        results = reg.search_modules("brut", category="scanner")
        assert len(results) == 0  # brutus is credential, not scanner


class TestRegistryCacheStaleness:
    def test_fresh_cache_is_not_stale(self, seeded_cache):
        reg = ModuleRegistry()
        assert reg._is_cache_stale() is False

    def test_old_cache_is_stale(self, seeded_cache):
        cache = seeded_cache / "registry.json"
        old_time = time.time() - 90000  # 25 hours ago
        os.utime(str(cache), (old_time, old_time))
        reg = ModuleRegistry()
        assert reg._is_cache_stale() is True


class TestVersionTracking:
    def test_record_and_get_version(self, tmp_home):
        reg = ModuleRegistry()
        reg.record_version("brutus", "v1.2.3", "/path/to/brutus")
        info = reg.get_version("brutus")
        assert info["version"] == "v1.2.3"
        assert info["path"] == "/path/to/brutus"
        assert "installed_at" in info

    def test_get_version_uninstalled_returns_none(self, tmp_home):
        reg = ModuleRegistry()
        assert reg.get_version("nonexistent") is None

    def test_get_all_versions(self, tmp_home):
        reg = ModuleRegistry()
        reg.record_version("brutus", "v1.0.0", "/a")
        reg.record_version("nuclei", "v3.0.0", "/b")
        versions = reg.get_all_versions()
        assert "brutus" in versions
        assert "nuclei" in versions

    def test_remove_version(self, tmp_home):
        reg = ModuleRegistry()
        reg.record_version("brutus", "v1.0.0", "/a")
        reg.remove_version("brutus")
        assert reg.get_version("brutus") is None


class TestRegistryAsInstallableTools:
    def test_get_installable_tools_dict(self, seeded_cache):
        """get_installable_tools returns a dict compatible with the old INSTALLABLE_TOOLS."""
        reg = ModuleRegistry()
        tools = reg.get_installable_tools()
        assert "brutus" in tools
        assert tools["brutus"]["repo"] == "praetorian-inc/brutus"
        assert "description" in tools["brutus"]

    def test_get_tool_aliases_dict(self, seeded_cache):
        """get_tool_aliases returns a dict compatible with the old TOOL_ALIASES."""
        reg = ModuleRegistry()
        aliases = reg.get_tool_aliases()
        assert "brutus" in aliases
        assert "target_type" in aliases["brutus"]
        assert "description" in aliases["brutus"]
        assert "capability" in aliases["brutus"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_registry.py -v --tb=short 2>&1 | head -30`

Expected: ImportError — `praetorian_cli.registry` does not exist yet.

- [ ] **Step 3: Implement registry.py**

Create `praetorian_cli/registry.py`:

```python
"""Module registry: fetch, cache, parse, and query the tool manifest."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_PRAETORIAN_DIR = os.path.join(os.path.expanduser("~"), ".praetorian")
CACHE_PATH = os.path.join(_PRAETORIAN_DIR, "registry.json")
VERSIONS_PATH = os.path.join(_PRAETORIAN_DIR, "versions.json")
BUNDLED_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "modules", "registry.json"
)

CACHE_TTL_SECONDS = 86400  # 24 hours

REGISTRY_URL = (
    "https://raw.githubusercontent.com/praetorian-inc/praetorian-cli"
    "/main/modules/registry.json"
)


class ModuleRegistry:
    def __init__(self):
        self._data: Optional[Dict] = None

    def _load(self) -> Dict:
        if self._data is not None:
            return self._data

        # Try cache first
        if os.path.isfile(CACHE_PATH):
            try:
                with open(CACHE_PATH) as f:
                    self._data = json.load(f)
                return self._data
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback to bundled
        if os.path.isfile(BUNDLED_REGISTRY_PATH):
            try:
                with open(BUNDLED_REGISTRY_PATH) as f:
                    self._data = json.load(f)
                return self._data
            except (json.JSONDecodeError, OSError):
                pass

        self._data = {"version": 1, "modules": {}}
        return self._data

    def _is_cache_stale(self) -> bool:
        if not os.path.isfile(CACHE_PATH):
            return True
        mtime = os.path.getmtime(CACHE_PATH)
        return (time.time() - mtime) > CACHE_TTL_SECONDS

    def refresh(self, force: bool = False) -> bool:
        if not force and not self._is_cache_stale():
            return False
        try:
            import urllib.request
            req = urllib.request.Request(REGISTRY_URL, headers={"User-Agent": "guard-cli"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w") as f:
                json.dump(data, f, indent=2)
            self._data = data
            return True
        except Exception:
            return False

    def get_modules(self) -> Dict[str, Dict]:
        return self._load().get("modules", {})

    def get_module(self, name: str) -> Optional[Dict]:
        modules = self.get_modules()
        mod = modules.get(name.lower())
        if mod is not None:
            return mod
        for key, val in modules.items():
            if key.lower() == name.lower():
                return val
        return None

    def search_modules(
        self,
        query: str = "",
        category: str = "",
    ) -> List[Dict[str, Any]]:
        modules = self.get_modules()
        results = []
        q = query.lower()

        for name, mod in modules.items():
            if category and mod.get("category", "") != category:
                continue
            if q:
                searchable = " ".join([
                    name,
                    mod.get("description", ""),
                    mod.get("category", ""),
                    " ".join(mod.get("tags", [])),
                ]).lower()
                if q not in searchable:
                    continue
            results.append({"name": name, **mod})

        results.sort(key=lambda r: r["name"])
        return results

    # -- Version tracking --

    def _load_versions(self) -> Dict:
        if os.path.isfile(VERSIONS_PATH):
            try:
                with open(VERSIONS_PATH) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_versions(self, versions: Dict):
        os.makedirs(os.path.dirname(VERSIONS_PATH), exist_ok=True)
        with open(VERSIONS_PATH, "w") as f:
            json.dump(versions, f, indent=2)

    def record_version(self, name: str, version: str, path: str):
        versions = self._load_versions()
        versions[name] = {
            "version": version,
            "path": path,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_versions(versions)

    def get_version(self, name: str) -> Optional[Dict]:
        return self._load_versions().get(name)

    def get_all_versions(self) -> Dict:
        return self._load_versions()

    def remove_version(self, name: str):
        versions = self._load_versions()
        versions.pop(name, None)
        self._save_versions(versions)

    # -- Backward-compat dict interfaces --

    def get_installable_tools(self) -> Dict[str, Dict]:
        modules = self.get_modules()
        return {
            name: {"repo": mod["repo"], "description": mod["description"]}
            for name, mod in modules.items()
        }

    def get_tool_aliases(self) -> Dict[str, Dict]:
        modules = self.get_modules()
        return {
            name: {
                "capability": name,
                "agent": name,
                "target_type": mod.get("target_type", "asset"),
                "description": mod["description"],
            }
            for name, mod in modules.items()
        }


_registry = None


def get_registry() -> ModuleRegistry:
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_registry.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/registry.py praetorian_cli/sdk/test/test_registry.py
git commit -m "feat(modules): registry module with fetch, cache, search, version tracking"
```

---

### Task 3: Wire `runners/local.py` to the Registry

**Files:**
- Modify: `praetorian_cli/runners/local.py:12-34` (replace `INSTALLABLE_TOOLS` dict)
- Modify: `praetorian_cli/runners/local.py:110-188` (add version recording in `install_tool`)

Replace the hardcoded `INSTALLABLE_TOOLS` dict with a function that reads from the registry. Record version on install.

- [ ] **Step 1: Run existing local runner tests to confirm they pass before changes**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_local_runner.py -v`

Expected: All existing tests PASS.

- [ ] **Step 2: Replace INSTALLABLE_TOOLS with registry-backed function**

In `praetorian_cli/runners/local.py`, replace lines 16-34 (the `INSTALLABLE_TOOLS` dict) with:

```python
def _get_installable_tools():
    from praetorian_cli.registry import get_registry
    return get_registry().get_installable_tools()


# Lazy property for backward compat — code that does `from runners.local import INSTALLABLE_TOOLS`
# gets a dict-like object that loads on first access.
class _LazyTools:
    def __init__(self):
        self._loaded = None

    def _ensure(self):
        if self._loaded is None:
            self._loaded = _get_installable_tools()
        return self._loaded

    def __contains__(self, key):
        return key in self._ensure()

    def __getitem__(self, key):
        return self._ensure()[key]

    def __iter__(self):
        return iter(self._ensure())

    def __len__(self):
        return len(self._ensure())

    def items(self):
        return self._ensure().items()

    def keys(self):
        return self._ensure().keys()

    def values(self):
        return self._ensure().values()

    def get(self, key, default=None):
        return self._ensure().get(key, default)


INSTALLABLE_TOOLS = _LazyTools()
```

- [ ] **Step 3: Add version recording to install_tool**

In `praetorian_cli/runners/local.py`, inside the `install_tool` function, after `os.chmod(binary_path, 0o755)` and before the cleanup section, add:

```python
    # Record version
    try:
        from praetorian_cli.registry import get_registry
        ver_result = subprocess.run(
            ['gh', 'release', 'view', '--repo', repo, '--json', 'tagName', '-q', '.tagName'],
            capture_output=True, text=True, timeout=15,
        )
        version_tag = ver_result.stdout.strip() if ver_result.returncode == 0 else 'unknown'
        get_registry().record_version(tool_name, version_tag, binary_path)
    except Exception:
        pass
```

- [ ] **Step 4: Run existing tests to confirm backward compat**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_local_runner.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`

Expected: All existing tests still PASS. The `_LazyTools` wrapper is dict-compatible.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/runners/local.py
git commit -m "refactor(modules): replace hardcoded INSTALLABLE_TOOLS with registry-backed loader"
```

---

### Task 4: Wire `handlers/run.py` to the Registry

**Files:**
- Modify: `praetorian_cli/handlers/run.py:1-30` (replace `FRIENDLY_NAMES`/`TOOL_ALIASES`)

Replace the hardcoded dicts with registry-backed equivalents.

- [ ] **Step 1: Run existing run CLI tests**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_run_cli.py -v`

Expected: All PASS.

- [ ] **Step 2: Replace FRIENDLY_NAMES and TOOL_ALIASES**

In `handlers/run.py`, replace the `FRIENDLY_NAMES` dict and `TOOL_ALIASES` construction (lines ~10-30) with:

```python
def _get_tool_aliases():
    from praetorian_cli.registry import get_registry
    return get_registry().get_tool_aliases()


class _LazyAliases:
    """Lazy-loading dict wrapper so `from handlers.run import TOOL_ALIASES` still works."""
    def __init__(self):
        self._loaded = None

    def _ensure(self):
        if self._loaded is None:
            self._loaded = _get_tool_aliases()
        return self._loaded

    def __contains__(self, key):
        return key in self._ensure()

    def __getitem__(self, key):
        return self._ensure()[key]

    def __setitem__(self, key, value):
        self._ensure()[key] = value

    def __iter__(self):
        return iter(self._ensure())

    def __len__(self):
        return len(self._ensure())

    def items(self):
        return self._ensure().items()

    def keys(self):
        return self._ensure().keys()

    def values(self):
        return self._ensure().values()

    def get(self, key, default=None):
        return self._ensure().get(key, default)


TOOL_ALIASES = _LazyAliases()
```

Remove the `FRIENDLY_NAMES` dict entirely (it was only used to seed `TOOL_ALIASES`).

- [ ] **Step 3: Run tests**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_run_cli.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add praetorian_cli/handlers/run.py
git commit -m "refactor(modules): replace hardcoded TOOL_ALIASES with registry-backed loader"
```

---

### Task 5: Create `guard module` CLI Commands

**Files:**
- Create: `praetorian_cli/sdk/test/test_module_cli.py`
- Create: `praetorian_cli/handlers/module.py`
- Modify: `praetorian_cli/main.py`

New `guard module` subcommand group with search, info, options, install, uninstall, update, installed, list.

- [ ] **Step 1: Write failing tests**

Create `praetorian_cli/sdk/test/test_module_cli.py`:

```python
"""Unit tests for `guard module` CLI commands."""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot

pytestmark = pytest.mark.cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    return sdk


SAMPLE_MODULES = {
    "brutus": {
        "repo": "praetorian-inc/brutus",
        "description": "Credential attacks across 20+ protocols",
        "category": "credential",
        "author": "Praetorian",
        "target_type": "asset",
        "options": {
            "protocol": {"type": "string", "description": "Target protocol", "required": False},
        },
        "tags": ["brute-force", "password"],
    },
    "nuclei": {
        "repo": "praetorian-inc/nuclei",
        "description": "Vulnerability scanner",
        "category": "scanner",
        "author": "Praetorian",
        "target_type": "asset",
        "options": {},
        "tags": ["vulnerability"],
    },
}


def _invoke(runner, fake_sdk, argv):
    obj = {"keychain": MagicMock(), "proxy": ""}
    with patch("praetorian_cli.sdk.chariot.Chariot", return_value=fake_sdk), \
         patch("praetorian_cli.handlers.cli_decorators.upgrade_check", lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, catch_exceptions=False)


class TestModuleSearch:
    def test_search_no_args_lists_all(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            result = _invoke(runner, fake_sdk, ["module", "search"])
        assert result.exit_code == 0
        assert "brutus" in result.output
        assert "nuclei" in result.output

    def test_search_with_query(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            result = _invoke(runner, fake_sdk, ["module", "search", "credential"])
        assert result.exit_code == 0
        assert "brutus" in result.output

    def test_search_with_category_filter(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            result = _invoke(runner, fake_sdk, ["module", "search", "--category", "scanner"])
        assert result.exit_code == 0
        assert "nuclei" in result.output

    def test_search_json_output(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            result = _invoke(runner, fake_sdk, ["module", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2


class TestModuleInfo:
    def test_info_existing_module(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            result = _invoke(runner, fake_sdk, ["module", "info", "brutus"])
        assert result.exit_code == 0
        assert "brutus" in result.output
        assert "credential" in result.output.lower() or "Credential" in result.output

    def test_info_unknown_module(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            result = _invoke(runner, fake_sdk, ["module", "info", "nonexistent"])
        assert result.exit_code != 0

    def test_info_json_output(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            result = _invoke(runner, fake_sdk, ["module", "info", "brutus", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "brutus"


class TestModuleInstalled:
    def test_installed_lists_tools(self, runner, fake_sdk):
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={"brutus": "/path/brutus"}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_all_versions", return_value={
                 "brutus": {"version": "v1.2.3", "path": "/path/brutus"}
             }):
            result = _invoke(runner, fake_sdk, ["module", "installed"])
        assert result.exit_code == 0
        assert "brutus" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_module_cli.py -v --tb=short 2>&1 | head -20`

Expected: ImportError or "No such command 'module'" errors.

- [ ] **Step 3: Implement handlers/module.py**

Create `praetorian_cli/handlers/module.py`:

```python
"""guard module — Metasploit-style module management commands."""

import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


@chariot.group()
def module():
    """Manage security tool modules

    \b
    Metasploit-style module management: search, inspect, install, and
    update security tools from the Guard module registry.
    """
    pass


@module.command("search")
@cli_handler
@click.argument("query", default="")
@click.option("--category", "-c", default="", help="Filter by category")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def search(sdk, query, category, as_json):
    """Search available modules by name, category, or keyword

    \b
    Example usages:
        guard module search
        guard module search credential
        guard module search --category scanner
        guard module search llm --json
    """
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed

    reg = get_registry()
    results = reg.search_modules(query, category=category)
    installed = list_installed()

    if as_json:
        for r in results:
            r["installed"] = r["name"] in installed
            ver = reg.get_version(r["name"])
            r["version"] = ver["version"] if ver else None
        print_json(results)
        return

    if not results:
        click.echo("No modules match the query.")
        return

    click.echo(f'\n{"Name":<18} {"Category":<14} {"Installed":<12} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 14} {"─" * 12} {"─" * 48}')

    for r in results:
        name = r["name"]
        cat = r.get("category", "")
        desc = r.get("description", "")
        if len(desc) > 48:
            desc = desc[:47] + "…"
        ver = reg.get_version(name)
        if name in installed:
            status = ver["version"] if ver else "yes"
        else:
            status = "—"
        click.echo(f"{name:<18} {cat:<14} {status:<12} {desc}")

    click.echo(f"\n{len(results)} modules")


@module.command("list")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def list_modules(sdk, as_json):
    """List all available modules (alias for search with no query)"""
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed

    reg = get_registry()
    results = reg.search_modules()
    installed = list_installed()

    if as_json:
        for r in results:
            r["installed"] = r["name"] in installed
            ver = reg.get_version(r["name"])
            r["version"] = ver["version"] if ver else None
        print_json(results)
        return

    click.echo(f'\n{"Name":<18} {"Category":<14} {"Installed":<12} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 14} {"─" * 12} {"─" * 48}')
    for r in results:
        name = r["name"]
        cat = r.get("category", "")
        desc = r.get("description", "")
        if len(desc) > 48:
            desc = desc[:47] + "…"
        ver = reg.get_version(name)
        if name in installed:
            status = ver["version"] if ver else "yes"
        else:
            status = "—"
        click.echo(f"{name:<18} {cat:<14} {status:<12} {desc}")
    click.echo(f"\n{len(results)} modules")


@module.command("info")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def info(sdk, name, as_json):
    """Show full details for a module

    \b
    Example usages:
        guard module info brutus
        guard module info nuclei --json
    """
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import is_installed, get_binary_path

    reg = get_registry()
    mod = reg.get_module(name)
    if not mod:
        error(f"Unknown module: {name}. Use 'guard module search' to find modules.")

    ver_info = reg.get_version(name.lower())

    if as_json:
        out = {"name": name.lower(), **mod}
        out["installed"] = is_installed(name.lower())
        out["version"] = ver_info["version"] if ver_info else None
        out["binary_path"] = get_binary_path(name.lower())
        print_json(out)
        return

    installed_str = "not installed"
    if is_installed(name.lower()):
        path = get_binary_path(name.lower())
        ver = ver_info["version"] if ver_info else "unknown"
        installed_str = f"{ver} ({path})"

    click.echo(f"\n  Name:        {name.lower()}")
    click.echo(f"  Category:    {mod.get('category', '')}")
    click.echo(f"  Author:      {mod.get('author', '')}")
    click.echo(f"  Repository:  {mod.get('repo', '')}")
    click.echo(f"  Installed:   {installed_str}")
    click.echo(f"  Target:      {mod.get('target_type', 'asset')}")
    click.echo(f"  Description: {mod.get('description', '')}")

    tags = mod.get("tags", [])
    if tags:
        click.echo(f"  Tags:        {', '.join(tags)}")

    options = mod.get("options", {})
    if options:
        click.echo(f"\n  Options:")
        for opt_name, opt_info in options.items():
            opt_type = opt_info.get("type", "string")
            opt_desc = opt_info.get("description", "")
            click.echo(f"    --{opt_name:<14} {opt_type:<8} {opt_desc}")

    click.echo(f"\n  Usage:")
    click.echo(f"    guard run tool {name.lower()} <target>")
    click.echo()


@module.command("options")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def options(sdk, name, as_json):
    """Show configurable options for a module

    \b
    Example: guard module options brutus
    """
    from praetorian_cli.registry import get_registry

    reg = get_registry()
    mod = reg.get_module(name)
    if not mod:
        error(f"Unknown module: {name}")

    opts = mod.get("options", {})

    if as_json:
        print_json(opts)
        return

    if not opts:
        click.echo(f"{name}: no configurable options.")
        return

    click.echo(f'\n{"Option":<18} {"Type":<10} {"Required":<10} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 10} {"─" * 10} {"─" * 40}')
    for opt_name, opt_info in opts.items():
        click.echo(
            f"--{opt_name:<16} {opt_info.get('type', 'string'):<10} "
            f"{'yes' if opt_info.get('required') else 'no':<10} "
            f"{opt_info.get('description', '')}"
        )
    click.echo()


@module.command("install")
@cli_handler
@click.argument("name")
@click.option("--force", is_flag=True, default=False, help="Reinstall even if present")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def install(sdk, name, force, as_json):
    """Install a module binary from GitHub releases

    \b
    Example usages:
        guard module install brutus
        guard module install all
        guard module install brutus --force
    """
    from praetorian_cli.runners.local import install_tool, INSTALLABLE_TOOLS, is_installed

    if name == "all":
        results = []
        for tool_name in sorted(INSTALLABLE_TOOLS):
            try:
                if not force and is_installed(tool_name):
                    if as_json:
                        results.append({"name": tool_name, "status": "already_installed"})
                    else:
                        click.echo(f"{tool_name}: already installed")
                else:
                    if not as_json:
                        click.echo(f"{tool_name}: installing...", nl=False)
                    path = install_tool(tool_name, force=force)
                    if as_json:
                        results.append({"name": tool_name, "status": "installed", "path": path})
                    else:
                        click.echo(f" {path}")
            except Exception as e:
                if as_json:
                    results.append({"name": tool_name, "status": "error", "error": str(e)})
                else:
                    click.echo(f" FAILED: {e}", err=True)
        if as_json:
            print_json(results)
        return

    try:
        if not as_json:
            click.echo(f"Installing {name}...")
        path = install_tool(name, force=force)
        if as_json:
            print_json({"name": name, "status": "installed", "path": path})
        else:
            click.echo(f"Installed: {path}")
    except Exception as e:
        if as_json:
            print_json({"name": name, "status": "error", "error": str(e)})
        else:
            error(str(e))


@module.command("uninstall")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def uninstall(sdk, name, as_json):
    """Remove an installed module binary

    \b
    Example: guard module uninstall brutus
    """
    import os
    from praetorian_cli.runners.local import get_binary_path, INSTALL_DIR
    from praetorian_cli.registry import get_registry

    path = get_binary_path(name)
    if not path:
        if as_json:
            print_json({"name": name, "status": "not_installed"})
        else:
            error(f"{name} is not installed.")
        return

    # Only remove from our install dir, not system binaries
    if not path.startswith(INSTALL_DIR):
        if as_json:
            print_json({"name": name, "status": "error", "error": "System binary, not managed by guard"})
        else:
            error(f"{name} at {path} is a system binary, not managed by guard module install.")
        return

    os.remove(path)
    get_registry().remove_version(name)

    if as_json:
        print_json({"name": name, "status": "uninstalled"})
    else:
        click.echo(f"Uninstalled: {name}")


@module.command("update")
@cli_handler
@click.argument("name", default="all")
@click.option("--registry", "update_registry", is_flag=True, default=False, help="Force refresh the registry")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def update(sdk, name, update_registry, as_json):
    """Update installed modules to latest release

    \b
    Example usages:
        guard module update
        guard module update brutus
        guard module update --registry
    """
    import subprocess
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import install_tool, is_installed, INSTALLABLE_TOOLS

    reg = get_registry()

    if update_registry:
        refreshed = reg.refresh(force=True)
        if not as_json:
            click.echo("Registry refreshed." if refreshed else "Registry refresh failed (using cached).")

    tools_to_update = sorted(INSTALLABLE_TOOLS) if name == "all" else [name]
    results = []

    for tool_name in tools_to_update:
        if not is_installed(tool_name):
            if name != "all":
                if as_json:
                    results.append({"name": tool_name, "status": "not_installed"})
                else:
                    click.echo(f"{tool_name}: not installed")
            continue

        mod = reg.get_module(tool_name)
        if not mod:
            continue

        current = reg.get_version(tool_name)
        current_ver = current["version"] if current else "unknown"

        # Check latest release
        try:
            ver_result = subprocess.run(
                ["gh", "release", "view", "--repo", mod["repo"], "--json", "tagName", "-q", ".tagName"],
                capture_output=True, text=True, timeout=15,
            )
            latest_ver = ver_result.stdout.strip() if ver_result.returncode == 0 else None
        except Exception:
            latest_ver = None

        if not latest_ver:
            if as_json:
                results.append({"name": tool_name, "status": "error", "error": "Could not check latest version"})
            else:
                click.echo(f"{tool_name}: could not check latest version")
            continue

        if latest_ver == current_ver:
            if as_json:
                results.append({"name": tool_name, "status": "up_to_date", "version": current_ver})
            elif name != "all":
                click.echo(f"{tool_name}: up to date ({current_ver})")
            continue

        # Update
        try:
            if not as_json:
                click.echo(f"{tool_name}: {current_ver} -> {latest_ver}...", nl=False)
            path = install_tool(tool_name, force=True)
            if as_json:
                results.append({"name": tool_name, "status": "updated", "from": current_ver, "to": latest_ver, "path": path})
            else:
                click.echo(f" done")
        except Exception as e:
            if as_json:
                results.append({"name": tool_name, "status": "error", "error": str(e)})
            else:
                click.echo(f" FAILED: {e}", err=True)

    if as_json:
        print_json(results)


@module.command("installed")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def installed(sdk, as_json):
    """List installed modules with versions"""
    from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS
    from praetorian_cli.registry import get_registry

    reg = get_registry()
    inst = list_installed()
    versions = reg.get_all_versions()

    if as_json:
        result = []
        for tool_name in sorted(INSTALLABLE_TOOLS):
            entry = {"name": tool_name, "installed": tool_name in inst}
            if tool_name in inst:
                entry["path"] = inst[tool_name]
                ver = versions.get(tool_name)
                entry["version"] = ver["version"] if ver else None
            result.append(entry)
        print_json(result)
        return

    click.echo(f'\n{"Tool":<18} {"Status":<12} {"Version":<12} {"Path"}')
    click.echo(f'{"─" * 18} {"─" * 12} {"─" * 12} {"─" * 50}')
    for tool_name in sorted(INSTALLABLE_TOOLS):
        if tool_name in inst:
            ver = versions.get(tool_name, {}).get("version", "—")
            click.echo(f"{tool_name:<18} {'installed':<12} {ver:<12} {inst[tool_name]}")
        else:
            click.echo(f"{tool_name:<18} {'—':<12} {'—':<12}")
    click.echo()
```

- [ ] **Step 4: Register in main.py**

In `praetorian_cli/main.py`, add after the existing handler imports (around line 14):

```python
import praetorian_cli.handlers.module
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_module_cli.py -v`

Expected: All PASS.

- [ ] **Step 6: Run all existing tests to confirm no regressions**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_run_cli.py praetorian_cli/sdk/test/test_local_runner.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add praetorian_cli/handlers/module.py praetorian_cli/main.py praetorian_cli/sdk/test/test_module_cli.py
git commit -m "feat(modules): guard module CLI commands — search, info, options, install, uninstall, update"
```

---

### Task 6: Add Console Commands (search, info, update)

**Files:**
- Create: `praetorian_cli/sdk/test/ui/test_console_modules.py`
- Modify: `praetorian_cli/ui/console/commands/tools.py`
- Modify: `praetorian_cli/ui/console/console.py`

Add `search`, `info`, `update` console commands that wire to the registry.

- [ ] **Step 1: Write failing tests**

Create `praetorian_cli/sdk/test/ui/test_console_modules.py`:

```python
"""Unit tests for console module commands (search, info, update)."""
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.ui.console.commands.tools import ToolCommands
from praetorian_cli.sdk.test.ui_mocks import MockConsole as _BaseMockConsole

pytestmark = pytest.mark.tui


SAMPLE_MODULES = {
    "brutus": {
        "repo": "praetorian-inc/brutus",
        "description": "Credential attacks across 20+ protocols",
        "category": "credential",
        "author": "Praetorian",
        "target_type": "asset",
        "options": {
            "protocol": {"type": "string", "description": "Target protocol", "required": False},
        },
        "tags": ["brute-force", "password"],
    },
    "nuclei": {
        "repo": "praetorian-inc/nuclei",
        "description": "Vulnerability scanner",
        "category": "scanner",
        "author": "Praetorian",
        "target_type": "asset",
        "options": {},
        "tags": ["vulnerability"],
    },
}


class MockConsole(_BaseMockConsole):
    def print(self, msg="", **kwargs):
        self.lines.append(str(msg))


class _FakeContext:
    active_tool = None
    account = "acct"
    _last_job_key = ""

    def apply_scope_to_message(self, msg):
        return msg


class _Harness(ToolCommands):
    def __init__(self, sdk=None):
        self.console = MockConsole()
        self.sdk = sdk or MagicMock()
        self.context = _FakeContext()
        self.colors = {
            "primary": "cyan", "accent": "magenta", "dim": "dim",
            "info": "blue", "success": "green", "warning": "yellow", "error": "red",
        }

    def _send_to_marcus(self, message):
        return ""

    def _wait_for_job(self, *a, **kw):
        pass


class TestConsoleSearch:
    def test_search_lists_all_modules(self):
        h = _Harness()
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            h._cmd_module_search([])
        output = "\n".join(h.console.lines)
        assert "brutus" in output
        assert "nuclei" in output

    def test_search_filters_by_query(self):
        h = _Harness()
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            h._cmd_module_search(["credential"])
        output = "\n".join(h.console.lines)
        assert "brutus" in output


class TestConsoleInfo:
    def test_info_shows_module_details(self):
        h = _Harness()
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES), \
             patch("praetorian_cli.runners.local.is_installed", return_value=False), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            h._cmd_module_info(["brutus"])
        output = "\n".join(h.console.lines)
        assert "brutus" in output
        assert "credential" in output.lower() or "Credential" in output

    def test_info_unknown_module(self):
        h = _Harness()
        with patch("praetorian_cli.registry.ModuleRegistry.get_modules", return_value=SAMPLE_MODULES):
            h._cmd_module_info(["nonexistent"])
        output = "\n".join(h.console.lines)
        assert "unknown" in output.lower() or "not found" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_modules.py -v --tb=short 2>&1 | head -20`

Expected: AttributeError — `_cmd_module_search` does not exist yet.

- [ ] **Step 3: Add module console commands to tools.py**

In `praetorian_cli/ui/console/commands/tools.py`, add these methods to the `ToolCommands` class (after the existing `_cmd_capabilities` method):

```python
    def _cmd_module_search(self, args):
        """Search modules from the registry."""
        from praetorian_cli.registry import get_registry
        from praetorian_cli.runners.local import list_installed

        reg = get_registry()
        query = args[0] if args else ''
        category = ''
        if '--category' in args:
            idx = args.index('--category')
            if idx + 1 < len(args):
                category = args[idx + 1]
                query = args[0] if args[0] != '--category' else ''

        results = reg.search_modules(query, category=category)
        installed = list_installed()

        if not results:
            self.console.print('[dim]No modules match the query.[/dim]')
            return

        table = Table(title=f'Modules ({len(results)})', border_style=self.colors['primary'])
        table.add_column('#', style=self.colors['dim'], width=4)
        table.add_column('Name', style=f'bold {self.colors["primary"]}', min_width=16)
        table.add_column('Category', style=self.colors['accent'])
        table.add_column('Installed', min_width=10)
        table.add_column('Description')

        self._module_list = []
        for i, r in enumerate(results, 1):
            name = r['name']
            ver = reg.get_version(name)
            if name in installed:
                status = f'[success]{ver["version"]}[/success]' if ver else '[success]yes[/success]'
            else:
                status = '[dim]—[/dim]'
            desc = r.get('description', '')
            if len(desc) > 50:
                desc = desc[:49] + '…'
            table.add_row(str(i), name, r.get('category', ''), status, desc)
            self._module_list.append(name)

        self.console.print(table)
        self.console.print(f'\n[dim]Use "info <name>" for details or "install <name>" to install.[/dim]')

    def _cmd_module_info(self, args):
        """Show full details for a module."""
        from praetorian_cli.registry import get_registry
        from praetorian_cli.runners.local import is_installed, get_binary_path

        if not args:
            self.console.print('[dim]Usage: info <module_name>[/dim]')
            return

        name = args[0].lower()
        reg = get_registry()
        mod = reg.get_module(name)
        if not mod:
            self.console.print(f'[error]Unknown module: {name}. Use "search" to find modules.[/error]')
            return

        ver_info = reg.get_version(name)
        installed_str = 'not installed'
        if is_installed(name):
            path = get_binary_path(name)
            ver = ver_info['version'] if ver_info else 'unknown'
            installed_str = f'{ver} ({path})'

        info_text = Text()
        info_text.append(f'Name:        ', style=self.colors['dim'])
        info_text.append(f'{name}\n', style=f'bold {self.colors["primary"]}')
        info_text.append(f'Category:    ', style=self.colors['dim'])
        info_text.append(f'{mod.get("category", "")}\n', style=self.colors['accent'])
        info_text.append(f'Author:      ', style=self.colors['dim'])
        info_text.append(f'{mod.get("author", "")}\n')
        info_text.append(f'Repository:  ', style=self.colors['dim'])
        info_text.append(f'{mod.get("repo", "")}\n')
        info_text.append(f'Installed:   ', style=self.colors['dim'])
        info_text.append(f'{installed_str}\n')
        info_text.append(f'Target:      ', style=self.colors['dim'])
        info_text.append(f'{mod.get("target_type", "asset")}\n')
        info_text.append(f'Description: ', style=self.colors['dim'])
        info_text.append(f'{mod.get("description", "")}\n')

        tags = mod.get('tags', [])
        if tags:
            info_text.append(f'Tags:        ', style=self.colors['dim'])
            info_text.append(f'{", ".join(tags)}\n')

        from rich.panel import Panel
        self.console.print(Panel(info_text, title=f'Module: {name}', border_style=self.colors['primary']))

        options = mod.get('options', {})
        if options:
            opt_table = Table(title='Options', border_style=self.colors['dim'])
            opt_table.add_column('Option', style=f'bold {self.colors["primary"]}')
            opt_table.add_column('Type', style=self.colors['accent'])
            opt_table.add_column('Required')
            opt_table.add_column('Description')
            for opt_name, opt_info in options.items():
                opt_table.add_row(
                    f'--{opt_name}',
                    opt_info.get('type', 'string'),
                    'yes' if opt_info.get('required') else 'no',
                    opt_info.get('description', ''),
                )
            self.console.print(opt_table)

    def _cmd_module_update(self, args):
        """Update installed modules to latest release."""
        import subprocess
        from praetorian_cli.registry import get_registry
        from praetorian_cli.runners.local import install_tool, is_installed, INSTALLABLE_TOOLS

        if '--registry' in args:
            reg = get_registry()
            refreshed = reg.refresh(force=True)
            self.console.print(
                '[success]Registry refreshed.[/success]' if refreshed
                else '[warning]Registry refresh failed (using cached).[/warning]'
            )
            return

        reg = get_registry()
        name = args[0].lower() if args else 'all'
        tools = sorted(INSTALLABLE_TOOLS) if name == 'all' else [name]

        updated = 0
        for tool_name in tools:
            if not is_installed(tool_name):
                if name != 'all':
                    self.console.print(f'[dim]{tool_name}: not installed[/dim]')
                continue

            mod = reg.get_module(tool_name)
            if not mod:
                continue

            current = reg.get_version(tool_name)
            current_ver = current['version'] if current else 'unknown'

            try:
                ver_result = subprocess.run(
                    ['gh', 'release', 'view', '--repo', mod['repo'],
                     '--json', 'tagName', '-q', '.tagName'],
                    capture_output=True, text=True, timeout=15,
                )
                latest = ver_result.stdout.strip() if ver_result.returncode == 0 else None
            except Exception:
                latest = None

            if not latest:
                self.console.print(f'[warning]{tool_name}: could not check latest version[/warning]')
                continue

            if latest == current_ver:
                if name != 'all':
                    self.console.print(f'[dim]{tool_name}: up to date ({current_ver})[/dim]')
                continue

            try:
                with self.console.status(f'Updating {tool_name} {current_ver} → {latest}...', spinner='dots'):
                    install_tool(tool_name, force=True)
                self.console.print(f'[success]{tool_name}: {current_ver} → {latest}[/success]')
                updated += 1
            except Exception as e:
                self.console.print(f'[error]{tool_name}: {e}[/error]')

        if name == 'all':
            self.console.print(f'[dim]{updated} module(s) updated.[/dim]')
```

You'll also need to add the `Table` and `Text` imports at the top of `tools.py` if not already present. Check that `Table` and `Text` are imported from `rich.table` and `rich.text` respectively (they already are at lines 8-9).

- [ ] **Step 4: Wire new commands in console.py dispatch table and CONSOLE_COMMANDS**

In `praetorian_cli/ui/console/console.py`:

Add to `CONSOLE_COMMANDS` list (around line 53, before `'help'`):
```python
    'update', 'module',
```

In the `_dispatch` method's `handlers` dict (around line 190), add:
```python
            'update': self._cmd_module_update,
            'module': self._cmd_module_dispatch,
```

Also add a `_cmd_module_dispatch` method to the `GuardConsole` class:
```python
    def _cmd_module_dispatch(self, args):
        """Route 'module <subcommand>' to the right handler."""
        if not args:
            self._cmd_module_search([])
            return
        sub = args[0].lower()
        rest = args[1:]
        routes = {
            'search': self._cmd_module_search,
            'info': self._cmd_module_info,
            'update': self._cmd_module_update,
            'install': self._cmd_install,
            'installed': self._cmd_installed,
            'options': self._cmd_options,
            'list': self._cmd_module_search,
        }
        handler = routes.get(sub)
        if handler:
            handler(rest)
        else:
            self.console.print(f'[dim]Unknown: module {sub}. Try: search, info, install, installed, update, options[/dim]')
```

Also update the existing `_cmd_info` dispatch in `search.py` or `console.py` to route to `_cmd_module_info` when a module name is given (check which file owns `_cmd_info`).

- [ ] **Step 5: Update help table**

In `console.py` `_cmd_help`, in the `[section]Security Tools (Metasploit-style)[/section]` section, add:
```python
        help_table.add_row('search [query]', 'Search module registry (name, category, tag)')
        help_table.add_row('info <module>', 'Show module details (options, version, author)')
        help_table.add_row('update [module|all]', 'Update installed modules to latest')
        help_table.add_row('module <subcmd>', 'Module management (search, info, install, update)')
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_modules.py praetorian_cli/sdk/test/ui/test_console_tools.py -v`

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add praetorian_cli/ui/console/commands/tools.py praetorian_cli/ui/console/console.py praetorian_cli/sdk/test/ui/test_console_modules.py
git commit -m "feat(modules): console search, info, update commands wired to registry"
```

---

### Task 7: Add MCP Tools for Claude Integration

**Files:**
- Modify: `praetorian_cli/sdk/mcp_server.py`

Add explicit module management MCP tools: `list_modules`, `module_info`, `install_module`, `run_module`.

- [ ] **Step 1: Add module MCP tools**

In `praetorian_cli/sdk/mcp_server.py`, add a new method `_register_module_tools` and call it from `__init__` after `self._register_tools()`:

```python
    def __init__(self, chariot_instance, allowable_tools: Optional[List[str]] = None):
        self.chariot = chariot_instance
        self.allowable_tools = allowable_tools
        self.server = Server("praetorian-cli")
        self.discovered_tools = {}
        self._discover_tools()
        self._register_tools()
        self._register_module_tools()
```

Then add the `_register_module_tools` method:

```python
    def _register_module_tools(self):
        """Register explicit module management MCP tools."""

        # Store module tool definitions for list_tools
        self._module_tools = {}

        self._module_tools["list_modules"] = Tool(
            name="list_modules",
            description="List all available Guard security modules with install status. "
                        "Returns name, category, description, install status, and version for each module.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (matches name, description, tags)"},
                    "category": {"type": "string", "description": "Filter by category (scanner, credential, recon, cloud, cicd, ai, supply-chain, api)"},
                },
            },
        )

        self._module_tools["module_info"] = Tool(
            name="module_info",
            description="Get full details for a Guard security module including options, version, and install path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name (e.g., brutus, nuclei, titus)"},
                },
                "required": ["name"],
            },
        )

        self._module_tools["install_module"] = Tool(
            name="install_module",
            description="Install a Guard security module binary from GitHub releases to ~/.praetorian/bin/.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name to install, or 'all'"},
                    "force": {"type": "boolean", "description": "Reinstall even if already present"},
                },
                "required": ["name"],
            },
        )

        self._module_tools["run_module"] = Tool(
            name="run_module",
            description="Execute an installed Guard security module against a target. "
                        "The module must be installed first (use install_module).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Module name"},
                    "target": {"type": "string", "description": "Target (IP, domain, URL, or Guard key)"},
                    "options": {"type": "object", "description": "Tool-specific options as key-value pairs"},
                },
                "required": ["name", "target"],
            },
        )

        # Patch the list_tools handler to include module tools
        original_list = self.server._tool_list_handler

        @self.server.list_tools()
        async def list_tools_with_modules() -> List[Tool]:
            base_tools = await original_list()
            return base_tools + list(self._module_tools.values())

        # Patch call_tool to handle module tools
        original_call = self._call_tool

        async def call_tool_with_modules(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if name in self._module_tools:
                return await self._handle_module_tool(name, arguments)
            return await original_call(name, arguments)

        self._call_tool = call_tool_with_modules

    async def _handle_module_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "list_modules":
                from praetorian_cli.registry import get_registry
                from praetorian_cli.runners.local import list_installed
                reg = get_registry()
                query = arguments.get("query", "")
                category = arguments.get("category", "")
                results = reg.search_modules(query, category=category)
                installed = list_installed()
                for r in results:
                    r["installed"] = r["name"] in installed
                    ver = reg.get_version(r["name"])
                    r["version"] = ver["version"] if ver else None
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "module_info":
                from praetorian_cli.registry import get_registry
                from praetorian_cli.runners.local import is_installed, get_binary_path
                reg = get_registry()
                mod_name = arguments["name"].lower()
                mod = reg.get_module(mod_name)
                if not mod:
                    return [TextContent(type="text", text=f"Unknown module: {mod_name}")]
                ver = reg.get_version(mod_name)
                out = {"name": mod_name, **mod}
                out["installed"] = is_installed(mod_name)
                out["version"] = ver["version"] if ver else None
                out["binary_path"] = get_binary_path(mod_name)
                return [TextContent(type="text", text=json.dumps(out, indent=2))]

            elif name == "install_module":
                from praetorian_cli.runners.local import install_tool, is_installed
                mod_name = arguments["name"].lower()
                force = arguments.get("force", False)
                if not force and is_installed(mod_name):
                    return [TextContent(type="text", text=json.dumps({"name": mod_name, "status": "already_installed"}))]
                path = install_tool(mod_name, force=force)
                return [TextContent(type="text", text=json.dumps({"name": mod_name, "status": "installed", "path": path}))]

            elif name == "run_module":
                from praetorian_cli.runners.local import LocalRunner, get_tool_plugin, is_installed
                mod_name = arguments["name"].lower()
                target = arguments["target"]
                options = arguments.get("options", {})
                if not is_installed(mod_name):
                    return [TextContent(type="text", text=f"Module {mod_name} is not installed. Use install_module first.")]
                plugin = get_tool_plugin(mod_name)
                extra_config = json.dumps(options) if options else ""
                args = plugin.build_args(target, extra_config)
                runner = LocalRunner(mod_name)
                result = runner.run(args, timeout=300)
                out = {
                    "name": mod_name,
                    "target": target,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                return [TextContent(type="text", text=json.dumps(out, indent=2))]

            return [TextContent(type="text", text=f"Unknown module tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error in {name}: {str(e)}")]
```

- [ ] **Step 2: Run existing MCP test to confirm no regression**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_mcp.py -v 2>&1 | tail -20`

Expected: Existing tests PASS (or skip if they require a live server).

- [ ] **Step 3: Commit**

```bash
git add praetorian_cli/sdk/mcp_server.py
git commit -m "feat(modules): MCP tools for module management — list, info, install, run"
```

---

### Task 8: Integration Test and Final Verification

**Files:**
- All previously created/modified files

Final sweep: run the full test suite, manually verify CLI commands work, check backward compat.

- [ ] **Step 1: Run the full test suite**

Run: `cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli && python -m pytest praetorian_cli/sdk/test/test_registry.py praetorian_cli/sdk/test/test_module_cli.py praetorian_cli/sdk/test/test_local_runner.py praetorian_cli/sdk/test/test_run_cli.py praetorian_cli/sdk/test/ui/test_console_tools.py praetorian_cli/sdk/test/ui/test_console_modules.py -v`

Expected: All PASS.

- [ ] **Step 2: Verify CLI commands work (smoke test)**

```bash
cd /Users/ajman/Documents/Tools/praetorian-claude/guard-platform/guard-cli
pip install -e . 2>/dev/null
guard module search 2>&1 | head -20
guard module info brutus 2>&1
guard module installed 2>&1 | head -10
guard module search --json 2>&1 | python -m json.tool | head -10
guard module info brutus --json 2>&1 | python -m json.tool
```

Expected: All commands produce clean output matching the spec.

- [ ] **Step 3: Verify backward compat**

```bash
guard run list 2>&1 | head -10
guard run installed 2>&1 | head -10
```

Expected: Old commands still work identically.

- [ ] **Step 4: Commit any fixes, then final commit**

If any fixes were needed, commit them. Then:

```bash
git log --oneline feat/module-system --not main
```

Expected: Clean commit history showing the feature progression.
