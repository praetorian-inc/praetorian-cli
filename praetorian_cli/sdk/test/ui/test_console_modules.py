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
