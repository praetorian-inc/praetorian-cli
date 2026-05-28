"""Unit tests for console module commands (search, info, update)."""
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.catalog import Capability
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

SAMPLE_CAPABILITIES = [
    Capability.from_api({
        "Name": "brutus",
        "Title": "Brutus Credential Attacks",
        "Description": "Credential attacks across 20+ protocols",
        "Category": ["credential"],
        "Surface": "network",
        "Target": ["asset"],
        "Version": "1.2.3",
        "Executor": "local",
        "Parameters": [
            {"Name": "protocol", "Description": "Target protocol", "Type": "string", "Required": False},
        ],
    }),
    Capability.from_api({
        "Name": "nuclei",
        "Title": "Nuclei Vulnerability Scanner",
        "Description": "Vulnerability scanner",
        "Category": ["scanner"],
        "Surface": "network",
        "Target": ["asset"],
        "Version": "2.0.0",
        "Executor": "local",
        "Parameters": [],
    }),
]


class MockConsole(_BaseMockConsole):
    def print(self, msg="", **kwargs):
        from rich.console import Console as _RichConsole
        from io import StringIO
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        if isinstance(msg, (Table, Panel, Text)):
            buf = StringIO()
            rc = _RichConsole(file=buf, highlight=False, markup=False)
            rc.print(msg)
            self.lines.append(buf.getvalue())
        else:
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
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None), \
             patch("praetorian_cli.registry.ModuleRegistry.is_local_only", return_value=False):
            h._cmd_module_search([])
        output = "\n".join(h.console.lines)
        assert "brutus" in output
        assert "nuclei" in output

    def test_search_filters_by_query(self):
        h = _Harness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None), \
             patch("praetorian_cli.registry.ModuleRegistry.is_local_only", return_value=False):
            h._cmd_module_search(["credential"])
        output = "\n".join(h.console.lines)
        assert "brutus" in output


class TestConsoleInfo:
    def test_info_shows_module_details(self):
        h = _Harness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES), \
             patch("praetorian_cli.runners.local.is_installed", return_value=False), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            h._cmd_module_info(["brutus"])
        output = "\n".join(h.console.lines)
        assert "brutus" in output
        assert "credential" in output.lower() or "Credential" in output

    def test_info_unknown_module(self):
        h = _Harness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES):
            h._cmd_module_info(["nonexistent"])
        output = "\n".join(h.console.lines)
        assert "unknown" in output.lower() or "not found" in output.lower()


class TestConsoleModuleNumberedLookup:
    def test_console_module_info_accepts_result_number(self):
        """After a search, 'info 1' resolves to the first result by number."""
        h = _Harness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES), \
             patch("praetorian_cli.runners.local.list_installed", return_value={}), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None), \
             patch("praetorian_cli.registry.ModuleRegistry.is_local_only", return_value=False):
            h._cmd_module_search([])  # populates self._module_list

        # The first capability in SAMPLE_CAPABILITIES is "brutus"
        assert hasattr(h, "_module_list"), "_module_list should be set after search"
        assert len(h._module_list) >= 1
        first_name = h._module_list[0]

        h.console.lines.clear()
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPABILITIES), \
             patch("praetorian_cli.runners.local.is_installed", return_value=False), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            h._cmd_module_info(["1"])

        output = "\n".join(h.console.lines)
        # Must NOT print "Unknown module: 1"
        assert "Unknown module: 1" not in output, (
            f"'info 1' should resolve to '{first_name}', not treat '1' as a name. Got:\n{output}"
        )
        # Must render info for the first capability
        assert first_name in output, (
            f"Expected '{first_name}' in output after 'info 1'. Got:\n{output}"
        )
