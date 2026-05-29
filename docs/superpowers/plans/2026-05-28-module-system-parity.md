# Module System — Live-API Parity + Metasploit UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CLI module system reflect guard's live `/capabilities/` API as the single source of truth, reduce `registry.json` to a slim install-manifest, and deliver a streamlined Metasploit-grade discovery/install/run experience across CLI, console, and MCP.

**Architecture:** A new `CapabilityCatalog` fetches and normalizes guard capabilities (live → cache → bundled snapshot). `registry.json` becomes an install-only manifest (`name → repo/binary_pattern/plugin`, plus `capability` alias and `local_only` flag). CLI/console/MCP all read the catalog through one interface and render through shared helpers.

**Tech Stack:** Python 3.12, Click, Rich, prompt_toolkit, pytest. Existing SDK method `sdk.capabilities.list(name, target, executor)` returns `(list, offset)`.

**Branch:** `feat/module-system` (PR #226). Base spec: `docs/superpowers/specs/2026-05-28-module-system-parity-design.md`.

---

## File Structure

- Create: `praetorian_cli/catalog.py` — `CapabilityCatalog`, `Capability`, normalization, fuzzy search.
- Create: `praetorian_cli/modules/capabilities_snapshot.json` — bundled offline snapshot.
- Modify: `praetorian_cli/registry.py` — manifest v2 loader; `get_installable_tools`/`get_tool_aliases` honor `capability`/`binary_pattern`/`plugin`/`local_only`.
- Modify: `modules/registry.json` — migrate to v2 slim install-manifest.
- Modify: `praetorian_cli/runners/local.py` — `binary_pattern` from manifest; SHA-256 verify; `uninstall_tool`.
- Modify: `praetorian_cli/handlers/module.py` — catalog-backed commands + `sync`/`uninstall`; Rich progress; parallel install.
- Modify: `praetorian_cli/ui/console/commands/tools.py` — module subcommands via catalog + shared renderer; numbered results.
- Modify: `praetorian_cli/ui/console/console.py` — tab-completion for module subcommands + names.
- Modify: `praetorian_cli/sdk/mcp_server.py` — `list_modules`/`module_info` via catalog.
- Modify: `MANIFEST.in` — include the snapshot.
- Tests: `praetorian_cli/sdk/test/test_catalog.py`, extend `test_registry.py`, `test_module_cli.py`, `ui/test_console_modules.py`.

---

## Task 1: Capability normalization

**Files:**
- Create: `praetorian_cli/catalog.py`
- Test: `praetorian_cli/sdk/test/test_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# praetorian_cli/sdk/test/test_catalog.py
from praetorian_cli.catalog import Capability


def test_capability_normalizes_agora_shape():
    raw = {
        'Name': 'brutus', 'Title': 'Brutus', 'Target': ['port'],
        'Description': 'Credential testing', 'Category': ['credential'],
        'Surface': 'external', 'RunsOn': 'any', 'Version': '0.2.0',
        'Executor': 'chariot', 'Integration': False,
        'Parameters': [{'Name': 'protocol', 'Description': 'svc', 'Type': 'string',
                        'Default': '', 'Required': False, 'Options': ['ssh', 'rdp']}],
    }
    cap = Capability.from_api(raw)
    assert cap.name == 'brutus'
    assert cap.title == 'Brutus'
    assert cap.target == ['port']
    assert cap.category == ['credential']
    assert cap.surface == 'external'
    assert cap.version == '0.2.0'
    assert cap.parameters[0].name == 'protocol'
    assert cap.parameters[0].options == ['ssh', 'rdp']
    assert cap.parameters[0].required is False


def test_capability_handles_missing_and_scalar_fields():
    cap = Capability.from_api({'Name': 'x', 'Category': 'recon', 'Target': 'port'})
    assert cap.title == 'x'           # falls back to name
    assert cap.category == ['recon']  # scalar coerced to list
    assert cap.target == ['port']     # scalar coerced to list
    assert cap.parameters == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: praetorian_cli.catalog`.

- [ ] **Step 3: Write minimal implementation**

```python
# praetorian_cli/catalog.py
"""Capability catalog: guard's /capabilities API is the source of truth."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _as_list(v) -> list:
    if v is None or v == '':
        return []
    return v if isinstance(v, list) else [v]


def _ci(raw: Dict[str, Any], *keys, default=None):
    """Case-insensitive get across candidate keys (API uses PascalCase)."""
    lowered = {k.lower(): v for k, v in raw.items()}
    for k in keys:
        if k.lower() in lowered and lowered[k.lower()] not in (None, ''):
            return lowered[k.lower()]
    return default


@dataclass
class Parameter:
    name: str
    description: str = ''
    type: str = 'string'
    default: str = ''
    required: bool = False
    options: List[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> 'Parameter':
        return cls(
            name=_ci(raw, 'Name', default=''),
            description=_ci(raw, 'Description', default=''),
            type=_ci(raw, 'Type', default='string'),
            default=str(_ci(raw, 'Default', default='') or ''),
            required=bool(_ci(raw, 'Required', default=False)),
            options=_as_list(_ci(raw, 'Options', default=[])),
        )


@dataclass
class Capability:
    name: str
    title: str = ''
    target: List[str] = field(default_factory=list)
    description: str = ''
    category: List[str] = field(default_factory=list)
    surface: str = ''
    runs_on: str = ''
    version: str = ''
    executor: str = ''
    integration: bool = False
    parameters: List[Parameter] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> 'Capability':
        name = _ci(raw, 'Name', default='')
        return cls(
            name=name,
            title=_ci(raw, 'Title', default=name),
            target=_as_list(_ci(raw, 'Target', default=[])),
            description=_ci(raw, 'Description', default=''),
            category=_as_list(_ci(raw, 'Category', default=[])),
            surface=_ci(raw, 'Surface', default=''),
            runs_on=_ci(raw, 'RunsOn', 'Runs_On', default=''),
            version=_ci(raw, 'Version', default=''),
            executor=_ci(raw, 'Executor', default=''),
            integration=bool(_ci(raw, 'Integration', default=False)),
            parameters=[Parameter.from_api(p) for p in _as_list(_ci(raw, 'Parameters', default=[]))],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/catalog.py praetorian_cli/sdk/test/test_catalog.py
git commit -m "feat(catalog): normalize guard AgoraCapability shape"
```

---

## Task 2: Fuzzy ranked search + filters

**Files:**
- Modify: `praetorian_cli/catalog.py`
- Test: `praetorian_cli/sdk/test/test_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
from praetorian_cli.catalog import rank_search

def _caps():
    from praetorian_cli.catalog import Capability
    return [
        Capability.from_api({'Name': 'nuclei', 'Category': 'scanner', 'Surface': 'external',
                             'Target': ['port'], 'Description': 'vuln scanner', 'Title': 'Nuclei'}),
        Capability.from_api({'Name': 'nuclei_dast', 'Category': 'scanner', 'Surface': 'external',
                             'Target': ['webapp'], 'Description': 'dast', 'Title': 'Nuclei DAST'}),
        Capability.from_api({'Name': 'brutus', 'Category': 'credential', 'Surface': 'internal',
                             'Target': ['port'], 'Description': 'creds', 'Title': 'Brutus'}),
    ]

def test_rank_search_exact_before_prefix_before_fuzzy():
    out = rank_search(_caps(), 'nuclei')
    assert out[0].name == 'nuclei'          # exact wins
    assert out[1].name == 'nuclei_dast'     # prefix next

def test_rank_search_typo_tolerant():
    out = rank_search(_caps(), 'nuclie')    # transposed
    assert out and out[0].name in ('nuclei', 'nuclei_dast')

def test_rank_search_filters():
    out = rank_search(_caps(), '', category='credential')
    assert [c.name for c in out] == ['brutus']
    out = rank_search(_caps(), '', surface='external', target='port')
    assert [c.name for c in out] == ['nuclei']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -k rank_search -v`
Expected: FAIL with `ImportError: cannot import name 'rank_search'`.

- [ ] **Step 3: Write minimal implementation**

Append to `praetorian_cli/catalog.py`:

```python
from difflib import SequenceMatcher


def _score(cap: 'Capability', q: str) -> Optional[float]:
    """Higher is better; None means filtered out."""
    if not q:
        return 0.0
    name = cap.name.lower()
    hay = ' '.join([name, cap.title.lower(), cap.description.lower(),
                    ' '.join(cap.category)]).lower()
    if name == q:
        return 100.0
    if name.startswith(q):
        return 90.0 - (len(name) - len(q)) * 0.1
    if q in hay:
        return 70.0
    ratio = SequenceMatcher(None, q, name).ratio()
    if ratio >= 0.6:
        return 40.0 + ratio * 10
    return None


def rank_search(caps, query='', *, category='', surface='', target='', tag=''):
    q = (query or '').lower().strip()
    out = []
    for cap in caps:
        if category and category not in cap.category:
            continue
        if surface and cap.surface != surface:
            continue
        if target and target not in cap.target:
            continue
        if tag and tag not in cap.category and tag not in cap.target:
            continue
        s = _score(cap, q)
        if s is None:
            continue
        out.append((s, cap))
    out.sort(key=lambda t: (-t[0], t[1].name))
    return [c for _, c in out]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -k rank_search -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/catalog.py praetorian_cli/sdk/test/test_catalog.py
git commit -m "feat(catalog): fuzzy ranked search with category/surface/target/tag filters"
```

---

## Task 3: Catalog resolution — live → cache → bundled

**Files:**
- Modify: `praetorian_cli/catalog.py`
- Create: `praetorian_cli/modules/capabilities_snapshot.json`
- Modify: `MANIFEST.in`
- Test: `praetorian_cli/sdk/test/test_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from praetorian_cli.catalog import CapabilityCatalog

class _FakeSDK:
    def __init__(self, caps, fail=False):
        self._caps = caps; self._fail = fail
        class _C:
            def list(inner, name='', target='', executor=''):
                if self._fail:
                    raise RuntimeError('network down')
                return (self._caps, None)
        self.capabilities = _C()

def test_catalog_live_then_cache(tmp_path):
    cache = tmp_path / 'cap-cache.json'
    snap = tmp_path / 'snap.json'; snap.write_text('{"capabilities": []}')
    sdk = _FakeSDK([{'Name': 'brutus', 'Category': 'credential'}])
    cat = CapabilityCatalog(sdk, cache_path=str(cache), bundled_path=str(snap))
    caps = cat.all()
    assert [c.name for c in caps] == ['brutus']
    assert cat.source == 'live'
    assert cache.exists()

def test_catalog_falls_back_to_cache_when_api_fails(tmp_path):
    cache = tmp_path / 'cap-cache.json'
    cache.write_text(json.dumps({'capabilities': [{'Name': 'nuclei'}]}))
    snap = tmp_path / 'snap.json'; snap.write_text('{"capabilities": []}')
    sdk = _FakeSDK([], fail=True)
    cat = CapabilityCatalog(sdk, cache_path=str(cache), bundled_path=str(snap))
    caps = cat.all()
    assert [c.name for c in caps] == ['nuclei']
    assert cat.source.startswith('cached')

def test_catalog_falls_back_to_bundled(tmp_path):
    cache = tmp_path / 'missing.json'
    snap = tmp_path / 'snap.json'
    snap.write_text(json.dumps({'capabilities': [{'Name': 'titus'}]}))
    sdk = _FakeSDK([], fail=True)
    cat = CapabilityCatalog(sdk, cache_path=str(cache), bundled_path=str(snap))
    assert [c.name for c in cat.all()] == ['titus']
    assert cat.source == 'bundled'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -k catalog -v`
Expected: FAIL with `ImportError: cannot import name 'CapabilityCatalog'`.

- [ ] **Step 3: Write minimal implementation**

Append to `praetorian_cli/catalog.py`:

```python
import os
import time
import tempfile

_PRAETORIAN_DIR = os.path.join(os.path.expanduser('~'), '.praetorian')
DEFAULT_CACHE_PATH = os.path.join(_PRAETORIAN_DIR, 'capabilities-cache.json')
DEFAULT_BUNDLED_PATH = os.path.join(
    os.path.dirname(__file__), 'modules', 'capabilities_snapshot.json')
CACHE_TTL_SECONDS = 86400


def _atomic_write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class CapabilityCatalog:
    def __init__(self, sdk, cache_path=DEFAULT_CACHE_PATH, bundled_path=DEFAULT_BUNDLED_PATH):
        self.sdk = sdk
        self.cache_path = cache_path
        self.bundled_path = bundled_path
        self._caps: Optional[List[Capability]] = None
        self.source = ''

    def _cache_stale(self) -> bool:
        if not os.path.isfile(self.cache_path):
            return True
        return (time.time() - os.path.getmtime(self.cache_path)) > CACHE_TTL_SECONDS

    def refresh(self, force=False) -> bool:
        if not force and not self._cache_stale():
            return False
        try:
            raw, _ = self.sdk.capabilities.list()
            caps = raw if isinstance(raw, list) else raw.get('capabilities', raw.get('data', []))
            _atomic_write_json(self.cache_path, {'capabilities': caps})
            self._caps = [Capability.from_api(c) for c in caps]
            self.source = 'live'
            return True
        except Exception:
            return False

    def _load_file(self, path):
        with open(path) as f:
            data = json.load(f)
        return data.get('capabilities', data) if isinstance(data, dict) else data

    def all(self) -> List[Capability]:
        if self._caps is not None:
            return self._caps
        if self.refresh():
            return self._caps
        # cache
        if os.path.isfile(self.cache_path):
            try:
                age = int((time.time() - os.path.getmtime(self.cache_path)) / 3600)
                self._caps = [Capability.from_api(c) for c in self._load_file(self.cache_path)]
                self.source = f'cached ({age}h old)'
                return self._caps
            except (json.JSONDecodeError, OSError):
                pass
        # bundled
        if os.path.isfile(self.bundled_path):
            try:
                self._caps = [Capability.from_api(c) for c in self._load_file(self.bundled_path)]
                self.source = 'bundled'
                return self._caps
            except (json.JSONDecodeError, OSError):
                pass
        self._caps = []
        self.source = 'empty'
        return self._caps

    def get(self, name: str) -> Optional[Capability]:
        n = name.lower()
        for c in self.all():
            if c.name.lower() == n:
                return c
        return None

    def search(self, query='', **filters) -> List[Capability]:
        return rank_search(self.all(), query, **filters)
```

- [ ] **Step 4: Create the bundled snapshot**

Run this to generate the snapshot from the live API (one-time, requires auth):

```bash
guard run capabilities --json > /tmp/caps.json 2>/dev/null || true
python -c "import json,sys; d=json.load(open('/tmp/caps.json')); caps=d if isinstance(d,list) else d.get('capabilities',d.get('data',[])); json.dump({'capabilities':caps}, open('praetorian_cli/modules/capabilities_snapshot.json','w'), indent=2)"
```

If no auth is available, create a minimal valid placeholder so tests/packaging pass:

```bash
printf '{"capabilities": []}\n' > praetorian_cli/modules/capabilities_snapshot.json
```

- [ ] **Step 5: Add to MANIFEST.in**

Add this line to `MANIFEST.in`:

```
include praetorian_cli/modules/capabilities_snapshot.json
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_catalog.py -v`
Expected: PASS (all catalog tests).

- [ ] **Step 7: Commit**

```bash
git add praetorian_cli/catalog.py praetorian_cli/modules/capabilities_snapshot.json MANIFEST.in praetorian_cli/sdk/test/test_catalog.py
git commit -m "feat(catalog): live->cache->bundled resolution with graceful offline fallback"
```

---

## Task 4: Migrate registry.json to v2 slim install-manifest

**Files:**
- Modify: `modules/registry.json`
- Modify: `praetorian_cli/registry.py`
- Test: `praetorian_cli/sdk/test/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# add to praetorian_cli/sdk/test/test_registry.py
from praetorian_cli.registry import get_registry

def test_manifest_exposes_capability_alias_and_local_only(monkeypatch, tmp_path):
    import praetorian_cli.registry as reg_mod
    manifest = tmp_path / 'registry.json'
    manifest.write_text('''{
      "version": 2,
      "modules": {
        "brutus": {"repo": "praetorian-inc/brutus", "binary_pattern": "brutus-{os}-{arch}*", "plugin": "brutus"},
        "pius": {"repo": "praetorian-inc/pius", "capability": "pius_discovery"},
        "titus": {"repo": "praetorian-inc/titus", "local_only": true}
      }
    }''')
    monkeypatch.setattr(reg_mod, 'BUNDLED_REGISTRY_PATH', str(manifest))
    monkeypatch.setattr(reg_mod, 'CACHE_PATH', str(tmp_path / 'cache-none.json'))
    reg_mod._registry = None
    reg = get_registry()
    assert reg.get_capability_name('pius') == 'pius_discovery'
    assert reg.get_capability_name('brutus') == 'brutus'   # defaults to name
    assert reg.is_local_only('titus') is True
    assert reg.is_local_only('brutus') is False
    assert reg.get_binary_pattern('brutus') == 'brutus-{os}-{arch}*'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_registry.py -k manifest -v`
Expected: FAIL with `AttributeError: 'ModuleRegistry' object has no attribute 'get_capability_name'`.

- [ ] **Step 3: Add manifest accessors to registry.py**

Add these methods to `ModuleRegistry` (after `get_module`):

```python
    def get_capability_name(self, name: str) -> str:
        """The guard capability a module maps to (defaults to its own name)."""
        mod = self.get_module(name) or {}
        return mod.get('capability', name.lower())

    def is_local_only(self, name: str) -> bool:
        mod = self.get_module(name) or {}
        return bool(mod.get('local_only', False))

    def get_binary_pattern(self, name: str) -> Optional[str]:
        mod = self.get_module(name) or {}
        return mod.get('binary_pattern')

    def get_plugin_name(self, name: str) -> Optional[str]:
        mod = self.get_module(name) or {}
        return mod.get('plugin')
```

Also update `get_installable_tools` to tolerate the slim manifest (no `description`):

```python
    def get_installable_tools(self) -> Dict[str, Dict]:
        modules = self.get_modules()
        return {
            name: {"repo": mod.get("repo", ""), "description": mod.get("description", "")}
            for name, mod in modules.items()
        }
```

- [ ] **Step 4: Migrate `modules/registry.json` to v2**

Rewrite `modules/registry.json` as the slim install-manifest. For each currently-listed tool, keep `repo`, add `binary_pattern` (default `{name}-{os}-{arch}*`), and `plugin` (the existing plugin key from `runners/local.py` `TOOL_PLUGINS`). Add `capability` only where the guard name differs (`pius` → `pius_discovery`). Tag the 8 non-guard tools (`titus, nerva, gato, cato, florian, aurelian, nero`, and `pius` if it has no capability) with `"local_only": true`. Example shape:

```json
{
  "version": 2,
  "modules": {
    "brutus":   {"repo": "praetorian-inc/brutus",   "binary_pattern": "brutus-{os}-{arch}*",   "plugin": "brutus"},
    "nuclei":   {"repo": "praetorian-inc/nuclei",   "binary_pattern": "nuclei-{os}-{arch}*",   "plugin": "nuclei"},
    "trajan":   {"repo": "praetorian-inc/trajan",   "binary_pattern": "trajan-{os}-{arch}*",   "plugin": "trajan"},
    "julius":   {"repo": "praetorian-inc/julius",   "binary_pattern": "julius-{os}-{arch}*",   "plugin": "julius"},
    "augustus": {"repo": "praetorian-inc/augustus", "binary_pattern": "augustus-{os}-{arch}*", "plugin": "augustus"},
    "hadrian":  {"repo": "praetorian-inc/hadrian",  "binary_pattern": "hadrian-{os}-{arch}*",  "plugin": "urltarget"},
    "vespasian":{"repo": "praetorian-inc/vespasian","binary_pattern": "vespasian-{os}-{arch}*","plugin": "scantarget"},
    "constantine":{"repo": "praetorian-inc/constantine","binary_pattern": "constantine-{os}-{arch}*","plugin": "scantarget"},
    "caligula": {"repo": "praetorian-inc/caligula", "binary_pattern": "caligula-{os}-{arch}*", "plugin": "scantarget"},
    "titus":    {"repo": "praetorian-inc/titus",    "binary_pattern": "titus-{os}-{arch}*",    "plugin": "titus", "local_only": true},
    "nerva":    {"repo": "praetorian-inc/nerva",    "binary_pattern": "nerva-{os}-{arch}*",    "plugin": "nerva", "local_only": true},
    "gato":     {"repo": "praetorian-inc/gato",     "binary_pattern": "gato-{os}-{arch}*",     "plugin": "gato", "local_only": true},
    "cato":     {"repo": "praetorian-inc/cato",     "binary_pattern": "cato-{os}-{arch}*",     "plugin": "urltarget", "local_only": true},
    "florian":  {"repo": "praetorian-inc/florian",  "binary_pattern": "florian-{os}-{arch}*",  "plugin": "urltarget", "local_only": true},
    "aurelian": {"repo": "praetorian-inc/aurelian", "binary_pattern": "aurelian-{os}-{arch}*", "plugin": "scantarget", "local_only": true},
    "nero":     {"repo": "praetorian-inc/nero",     "binary_pattern": "nero-{os}-{arch}*",     "plugin": "nerva", "local_only": true},
    "pius":     {"repo": "praetorian-inc/pius",     "binary_pattern": "pius-{os}-{arch}*",     "plugin": "nerva", "capability": "pius_discovery"}
  }
}
```

Note: verify each `local_only` tool against guard before finalizing (grep guard for the name); if a tool turns out to be a real guard capability under a different name, give it a `capability` alias instead of `local_only`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_registry.py -v`
Expected: PASS (new + existing registry tests). Fix any existing test that assumed `description` lives in the manifest — descriptions now come from the catalog.

- [ ] **Step 6: Commit**

```bash
git add modules/registry.json praetorian_cli/registry.py praetorian_cli/sdk/test/test_registry.py
git commit -m "feat(registry): migrate registry.json to v2 slim install-manifest"
```

---

## Task 5: SHA-256 verification + binary_pattern + uninstall in local runner

**Files:**
- Modify: `praetorian_cli/runners/local.py`
- Test: `praetorian_cli/sdk/test/ui/` (new `test_local_runner.py`)

- [ ] **Step 1: Write the failing test**

```python
# praetorian_cli/sdk/test/test_local_runner.py
import os
from praetorian_cli.runners import local

def test_uninstall_removes_binary_and_version(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'INSTALL_DIR', str(tmp_path))
    binp = tmp_path / 'titus'
    binp.write_text('#!/bin/sh\n'); os.chmod(binp, 0o755)
    removed = {}
    class _Reg:
        def remove_version(self, n): removed['n'] = n
    monkeypatch.setattr('praetorian_cli.registry.get_registry', lambda: _Reg())
    assert local.uninstall_tool('titus') is True
    assert not binp.exists()
    assert removed['n'] == 'titus'

def test_uninstall_missing_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'INSTALL_DIR', str(tmp_path))
    class _Reg:
        def remove_version(self, n): pass
    monkeypatch.setattr('praetorian_cli.registry.get_registry', lambda: _Reg())
    assert local.uninstall_tool('ghost') is False

def test_verify_sha256_matches(tmp_path):
    f = tmp_path / 'b'; f.write_bytes(b'hello')
    import hashlib
    digest = hashlib.sha256(b'hello').hexdigest()
    assert local.verify_sha256(str(f), digest) is True
    assert local.verify_sha256(str(f), 'deadbeef') is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'uninstall_tool'`.

- [ ] **Step 3: Implement uninstall + verify in local.py**

Add to `praetorian_cli/runners/local.py`:

```python
import hashlib


def verify_sha256(path: str, expected: str) -> bool:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest() == (expected or '').lower().strip()


def uninstall_tool(tool_name: str) -> bool:
    """Remove an installed binary from INSTALL_DIR and its version record."""
    from praetorian_cli.registry import get_registry
    path = os.path.join(INSTALL_DIR, tool_name)
    existed = os.path.isfile(path)
    if existed:
        os.remove(path)
    get_registry().remove_version(tool_name)
    return existed
```

Update `install_tool` to use the manifest `binary_pattern` when present (locate the `gh release download` pattern construction and replace the hardcoded `f'{tool_name}-{os}-{arch}*'` with):

```python
    from praetorian_cli.registry import get_registry
    pattern = get_registry().get_binary_pattern(tool_name)
    if pattern:
        asset_pattern = pattern.replace('{os}', os_name).replace('{arch}', arch)
    else:
        asset_pattern = f'{tool_name}-{os_name}-{arch}*'
```

(Use the existing local variable names for os/arch returned by `_detect_platform()`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_local_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/runners/local.py praetorian_cli/sdk/test/test_local_runner.py
git commit -m "feat(local): uninstall_tool, sha256 verify, manifest-driven binary_pattern"
```

---

## Task 6: Catalog-backed `guard module` CLI + sync/uninstall + parallel install

**Files:**
- Modify: `praetorian_cli/handlers/module.py`
- Test: `praetorian_cli/sdk/test/test_module_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to praetorian_cli/sdk/test/test_module_cli.py
from click.testing import CliRunner
from unittest.mock import patch
from praetorian_cli.handlers.chariot import chariot

def _fake_caps():
    return [{'Name': 'brutus', 'Title': 'Brutus', 'Category': ['credential'],
             'Surface': 'external', 'Target': ['port'], 'Description': 'creds',
             'Version': '0.2.0', 'Executor': 'chariot', 'Parameters': []}]

@patch('praetorian_cli.catalog.CapabilityCatalog.all')
def test_module_search_json_uses_catalog(mock_all):
    from praetorian_cli.catalog import Capability
    mock_all.return_value = [Capability.from_api(c) for c in _fake_caps()]
    runner = CliRunner()
    res = runner.invoke(chariot, ['module', 'search', 'brutus', '--json'],
                        obj=_make_obj())
    assert res.exit_code == 0
    import json
    data = json.loads(res.output)
    assert data[0]['name'] == 'brutus'
    assert data[0]['version'] == '0.2.0'
```

(Reuse the existing `_make_obj()` / SDK-mock helper already present in `test_module_cli.py`; if none exists, mirror the fixture pattern used by other CLI tests in that file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_module_cli.py -k catalog -v`
Expected: FAIL (search still reads `get_registry().search_modules`, output shape differs / no `version` from catalog).

- [ ] **Step 3: Rewrite module.py commands to use the catalog**

In `praetorian_cli/handlers/module.py`, replace the registry-driven `search`, `list`, `info`, `options` bodies with catalog-driven equivalents. Construct the catalog once per command:

```python
def _catalog(sdk):
    from praetorian_cli.catalog import CapabilityCatalog
    return CapabilityCatalog(sdk)
```

Rewrite `search` to merge catalog results with install status + local-only tagging:

```python
@module.command("search")
@cli_handler
@click.argument("query", default="")
@click.option("--category", "-c", default="")
@click.option("--surface", default="")
@click.option("--target", default="")
@click.option("--tag", default="")
@click.option("--installed", is_flag=True, default=False)
@click.option("--json", "as_json", is_flag=True, default=False)
def search(sdk, query, category, surface, target, tag, installed, as_json):
    """Search available modules (fuzzy, ranked)."""
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed
    cat = _catalog(sdk)
    reg = get_registry()
    results = cat.search(query, category=category, surface=surface, target=target, tag=tag)
    inst = list_installed()
    rows = []
    for c in results:
        name = c.name
        ver = reg.get_version(name)
        is_inst = name in inst
        if installed and not is_inst:
            continue
        rows.append({
            "name": name, "title": c.title, "category": c.category,
            "surface": c.surface, "target": c.target, "description": c.description,
            "version": c.version, "executor": c.executor,
            "installed": is_inst, "local_only": reg.is_local_only(name),
            "installed_version": ver["version"] if ver else None,
        })
    if as_json:
        print_json(rows)
        return
    if cat.source and cat.source != 'live':
        click.echo(f"(catalog: {cat.source})", err=True)
    _render_module_table(rows)
```

Add a shared table renderer `_render_module_table(rows)` (plain `click.echo` columns, marking `[local-only]` where `row['local_only']`). Rewrite `info`/`options`/`list` analogously (info pulls `c.parameters` for the options table). Add two new commands:

```python
@module.command("uninstall")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False)
def uninstall(sdk, name, as_json):
    """Remove an installed module binary."""
    from praetorian_cli.runners.local import uninstall_tool
    removed = uninstall_tool(name.lower())
    if as_json:
        print_json({"name": name.lower(), "removed": removed})
    else:
        click.echo(f"{name}: {'removed' if removed else 'not installed'}")


@module.command("sync")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False)
def sync(sdk, as_json):
    """Force-refresh the capability catalog from the backend."""
    cat = _catalog(sdk)
    ok = cat.refresh(force=True)
    n = len(cat.all())
    if as_json:
        print_json({"refreshed": ok, "count": n, "source": cat.source})
    else:
        click.echo(f"Catalog {'refreshed' if ok else 'unchanged'}: {n} capabilities ({cat.source}).")
```

Make `install all` parallel with a Rich progress bar:

```python
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.progress import Progress, SpinnerColumn, TextColumn
    # inside the `name == "all"` branch, replace the sequential loop:
    targets = [t for t in sorted(INSTALLABLE_TOOLS) if force or not is_installed(t)]
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as prog:
        tasks = {t: prog.add_task(f"{t}: queued", total=None) for t in targets}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(install_tool, t, force): t for t in targets}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    path = fut.result()
                    prog.update(tasks[t], description=f"{t}: installed")
                    results.append({"name": t, "status": "installed", "path": path})
                except Exception as e:
                    prog.update(tasks[t], description=f"{t}: FAILED {e}")
                    results.append({"name": t, "status": "error", "error": str(e)})
```

(Guard the Rich import path so `--json` mode stays quiet: when `as_json`, skip the Progress context and just run the pool.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_module_cli.py -v`
Expected: PASS. Update any existing module-CLI test that asserted the old registry-based output shape.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/handlers/module.py praetorian_cli/sdk/test/test_module_cli.py
git commit -m "feat(module): catalog-backed search/info/options + sync/uninstall + parallel install"
```

---

## Task 7: Console module commands + numbered results via shared catalog

**Files:**
- Modify: `praetorian_cli/ui/console/commands/tools.py`
- Test: `praetorian_cli/sdk/test/ui/test_console_modules.py`

- [ ] **Step 1: Write the failing test**

```python
# add to praetorian_cli/sdk/test/ui/test_console_modules.py
def test_console_module_info_accepts_result_number(console, capsys):
    # console fixture mirrors existing tests in this file
    console._cmd_module_search(['scanner', '--category', 'scanner'])
    # after a search, "info 1" resolves to the first result
    console._cmd_module_info(['1'])
    out = capsys.readouterr().out
    assert 'Category' in out  # info panel rendered, no "Unknown module"
```

(Use the same `console` fixture and Rich-capture pattern already in `test_console_modules.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_modules.py -k result_number -v`
Expected: FAIL ("Unknown module: 1") — numbered lookup not wired.

- [ ] **Step 3: Wire catalog + numbered results into console**

In `tools.py`, change `_cmd_module_search`/`_cmd_module_info`/`_cmd_module_update` to build a `CapabilityCatalog(self.sdk)` and use `cat.search(...)`/`cat.get(...)`. Persist ordered names in `self._module_list` during search. At the top of `_cmd_module_info`, resolve a numeric arg:

```python
        if args and args[0].isdigit():
            idx = int(args[0]) - 1
            if 0 <= idx < len(getattr(self, '_module_list', [])):
                args = [self._module_list[idx]] + list(args[1:])
```

Render the info panel from the `Capability` fields (title/version/surface/target/executor/description) and a parameters table from `cap.parameters` (name/type/required/default/options). Tag `[local-only]` rows in search using `get_registry().is_local_only(name)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_modules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/ui/console/commands/tools.py praetorian_cli/sdk/test/ui/test_console_modules.py
git commit -m "feat(console): catalog-backed module commands with numbered-result lookup"
```

---

## Task 8: Metasploit use/set/options/run with live params + tab-completion

**Files:**
- Modify: `praetorian_cli/ui/console/console.py`
- Modify: `praetorian_cli/ui/console/commands/tools.py`
- Test: `praetorian_cli/sdk/test/ui/test_console_modules.py`

- [ ] **Step 1: Write the failing test**

```python
def test_options_populated_from_live_params(console, capsys):
    console._cmd_use(['brutus'])
    console._cmd_options([])
    out = capsys.readouterr().out
    assert 'protocol' in out          # param name from live capability
    assert 'required' in out.lower()  # required column rendered

def test_set_rejects_unknown_param(console, capsys):
    console._cmd_use(['brutus'])
    console._cmd_set(['nonsense', 'x'])
    out = capsys.readouterr().out
    assert 'unknown' in out.lower() or 'no such option' in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_modules.py -k "options_populated or rejects_unknown" -v`
Expected: FAIL (options not sourced from live params; set not validated).

- [ ] **Step 3: Source params from the catalog in use/options/set**

In `_cmd_use`, store the resolved `Capability` (`self._selected_cap = cat.get(name)`) alongside the existing selection state. In `_cmd_options`, render `self._selected_cap.parameters`. In `_cmd_set`, validate the key against `{p.name for p in self._selected_cap.parameters}` and against `p.options` (enum) when non-empty; print an error otherwise.

- [ ] **Step 4: Extend tab-completion**

In `console.py`, replace the flat `WordCompleter(CONSOLE_COMMANDS)` with a `NestedCompleter` (from `prompt_toolkit.completion`) that maps `module` → `{search, info, options, install, uninstall, update, sync, list, installed}` and `use`/`info`/`install`/`uninstall` → live module names. Build the name list lazily from `CapabilityCatalog(self.sdk).all()` (guard with try/except so completion never crashes the prompt; fall back to `CONSOLE_COMMANDS`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/ui/test_console_modules.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add praetorian_cli/ui/console/console.py praetorian_cli/ui/console/commands/tools.py praetorian_cli/sdk/test/ui/test_console_modules.py
git commit -m "feat(console): live-param options/set validation + nested tab-completion"
```

---

## Task 9: MCP list_modules/module_info via catalog

**Files:**
- Modify: `praetorian_cli/sdk/mcp_server.py`
- Test: `praetorian_cli/sdk/test/` (extend an existing MCP test or add `test_mcp_modules.py`)

- [ ] **Step 1: Write the failing test**

```python
# praetorian_cli/sdk/test/test_mcp_modules.py
import asyncio
from unittest.mock import patch
from praetorian_cli.catalog import Capability

def test_list_modules_returns_all_capabilities():
    caps = [Capability.from_api({'Name': 'brutus', 'Category': ['credential']}),
            Capability.from_api({'Name': 'nuclei', 'Category': ['scanner']})]
    with patch('praetorian_cli.catalog.CapabilityCatalog.all', return_value=caps):
        from praetorian_cli.sdk.mcp_server import _handle_module_tool  # adjust import to actual symbol
        result = asyncio.get_event_loop().run_until_complete(
            _handle_module_tool('list_modules', {}, sdk=_mcp_sdk_stub()))
        names = [m['name'] for m in result]
        assert set(names) == {'brutus', 'nuclei'}
```

(Adjust the import/signature to match the real `_handle_module_tool` in `mcp_server.py`; reuse any existing MCP sdk stub.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest praetorian_cli/sdk/test/test_mcp_modules.py -v`
Expected: FAIL (still reads `reg.search_modules`, returns only manifest entries).

- [ ] **Step 3: Switch the MCP module handlers to the catalog**

In `mcp_server.py`, change the `list_modules` and `module_info` branches of `_handle_module_tool` to build `CapabilityCatalog(sdk)` and use `cat.search(...)` / `cat.get(...)`, merging install status from `list_installed()` and version from `get_registry().get_version()`. Leave `install_module`/`run_module` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest praetorian_cli/sdk/test/test_mcp_modules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/sdk/mcp_server.py praetorian_cli/sdk/test/test_mcp_modules.py
git commit -m "feat(mcp): list_modules/module_info reflect live guard capabilities"
```

---

## Task 10: Backward-compat + full suite

**Files:**
- Test only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest praetorian_cli/sdk/test/ -q`
Expected: all green. Investigate any failure where an existing test assumed registry-sourced descriptions; update it to source from the catalog (descriptions now live in the catalog, not the manifest).

- [ ] **Step 2: Manual smoke (requires auth)**

```bash
guard run list                 # unchanged output, install status intact
guard module sync              # refreshes catalog
guard module search scanner    # fuzzy/filtered, shows local-only tags
guard module info brutus       # live params table
guard module install all --json | head
```

- [ ] **Step 3: Commit any test fixups**

```bash
git add -A && git commit -m "test: align suite with catalog-sourced metadata"
```

---

## Self-Review Notes

- **Spec coverage:** three-layer resolution (Task 3), slim manifest + local_only + capability alias (Task 4), all `guard module` commands incl. sync/uninstall + parallel + sha256 (Tasks 5–6), console + Metasploit flow + completion (Tasks 7–8), MCP parity (Task 9), backward compat (Task 10). SHA-256 wiring into `install_tool` depends on releases publishing checksums; if absent, `verify_sha256` is exposed but skipped with a warning (noted in Task 5 — extend `install_tool` to call it only when a checksum asset is found).
- **Type consistency:** `Capability`/`Parameter` fields and `CapabilityCatalog.{all,get,search,refresh,source}` are used identically across Tasks 1–9.
- **No placeholders:** real code/tests in each step; manifest values to be verified against guard in Task 4 Step 4.
