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
