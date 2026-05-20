"""Module registry: fetch, cache, parse, and query the tool manifest."""

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_MAX_REGISTRY_SIZE = 1024 * 1024  # 1 MB

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
                raw = resp.read(_MAX_REGISTRY_SIZE + 1)
                if len(raw) > _MAX_REGISTRY_SIZE:
                    return False
                data = json.loads(raw.decode())
            if not isinstance(data.get("modules"), dict):
                return False
            self._atomic_write(CACHE_PATH, data)
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

    @staticmethod
    def _atomic_write(path: str, data: Dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

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
        self._atomic_write(VERSIONS_PATH, versions)

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
