"""Unit tests for console module commands (search, info, update)."""
from unittest.mock import MagicMock, patch

import pytest

from praetorian_cli.catalog import Capability
from praetorian_cli.ui.console.commands.tools import ToolCommands
from praetorian_cli.ui.console.commands.context import ContextCommands
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
        "Name": "brutus-with-enum",
        "Title": "Brutus with enum param",
        "Description": "Test capability with required param + enum options",
        "Category": ["credential"],
        "Surface": "network",
        "Target": ["asset"],
        "Version": "1.0.0",
        "Executor": "local",
        "Parameters": [
            {"Name": "protocol", "Description": "svc", "Type": "string", "Required": True,
             "Options": ["ssh", "rdp"]},
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


# ---------------------------------------------------------------------------
# Harness that mixes in both ContextCommands and ToolCommands to test use/set/options
# ---------------------------------------------------------------------------

class _FullFakeContext:
    """A richer fake context that includes all fields used by use/options/set."""
    active_tool = None
    account = "acct"
    _last_job_key = ""
    target = None
    scope = None
    mode = "query"
    verbose = False
    active_agent = None
    conversation_id = ""
    active_tool_config = {}

    def apply_scope_to_message(self, msg):
        return msg

    def clear_tool(self):
        self.active_tool = None
        self.target = None
        self.active_tool_config = {}

    def clear_conversation(self):
        pass


class _ContextHarness(ContextCommands, ToolCommands):
    """Harness that covers the Metasploit-style use/options/set commands."""

    def __init__(self, sdk=None):
        from unittest.mock import MagicMock
        self.console = MockConsole()
        self.sdk = sdk or MagicMock()
        self.context = _FullFakeContext()
        self.colors = {
            "primary": "cyan", "accent": "magenta", "dim": "dim",
            "info": "blue", "success": "green", "warning": "yellow", "error": "red",
        }

    # Stubs for cross-mixin calls not exercised in these tests
    def _cmd_run(self, args):
        pass

    def _cmd_switch(self, args):
        pass

    def _send_to_marcus(self, message):
        return ""

    def _wait_for_job(self, *a, **kw):
        pass

    def _show_engagement_status(self):
        pass


# Use a capability that has a *required* parameter with an enum (Options list)
_BRUTUS_WITH_ENUM = Capability.from_api({
    "Name": "brutus",
    "Title": "Brutus Credential Attacks",
    "Description": "Credential attacks across 20+ protocols",
    "Category": ["credential"],
    "Surface": "network",
    "Target": ["asset"],
    "Version": "1.2.3",
    "Executor": "local",
    "Parameters": [
        {
            "Name": "protocol",
            "Description": "svc",
            "Type": "string",
            "Required": True,
            "Options": ["ssh", "rdp"],
        }
    ],
})


class TestOptionsPopulatedFromLiveParams:
    def test_options_populated_from_live_params(self):
        """After 'use brutus', 'options' must render the live capability params."""
        h = _ContextHarness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.get", return_value=_BRUTUS_WITH_ENUM), \
             patch("praetorian_cli.handlers.run.TOOL_ALIASES", {"brutus": {
                 "capability": "brutus",
                 "agent": None,
                 "target_type": "asset",
                 "description": "Credential attacks",
                 "default_config": {},
             }}):
            h._cmd_use(["brutus"])
            h.console.lines.clear()
            h._cmd_options([])

        output = "\n".join(h.console.lines)
        assert "protocol" in output, f"Expected 'protocol' in options output. Got:\n{output}"
        # Required indicator should appear — 'yes' for required params
        assert "yes" in output.lower(), f"Expected required indicator in options output. Got:\n{output}"

    def test_set_rejects_unknown_param(self):
        """After 'use brutus', 'set nonsense x' must print an error containing 'unknown'."""
        h = _ContextHarness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.get", return_value=_BRUTUS_WITH_ENUM), \
             patch("praetorian_cli.handlers.run.TOOL_ALIASES", {"brutus": {
                 "capability": "brutus",
                 "agent": None,
                 "target_type": "asset",
                 "description": "Credential attacks",
                 "default_config": {},
             }}):
            h._cmd_use(["brutus"])
            h.console.lines.clear()
            h._cmd_set(["nonsense", "x"])

        output = "\n".join(h.console.lines)
        assert "unknown" in output.lower(), (
            f"Expected 'unknown' in error output for invalid param. Got:\n{output}"
        )

    def test_set_rejects_bad_enum_value(self):
        """After 'use brutus', 'set protocol telnet' (not in enum) must print an error."""
        h = _ContextHarness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.get", return_value=_BRUTUS_WITH_ENUM), \
             patch("praetorian_cli.handlers.run.TOOL_ALIASES", {"brutus": {
                 "capability": "brutus",
                 "agent": None,
                 "target_type": "asset",
                 "description": "Credential attacks",
                 "default_config": {},
             }}):
            h._cmd_use(["brutus"])
            h.console.lines.clear()
            h._cmd_set(["protocol", "telnet"])

        output = "\n".join(h.console.lines)
        assert any(word in output.lower() for word in ("allowed", "invalid", "ssh", "rdp")), (
            f"Expected enum error mentioning allowed values. Got:\n{output}"
        )

    def test_set_accepts_valid_enum_value(self):
        """After 'use brutus', 'set protocol ssh' must be accepted without error."""
        h = _ContextHarness()
        with patch("praetorian_cli.catalog.CapabilityCatalog.get", return_value=_BRUTUS_WITH_ENUM), \
             patch("praetorian_cli.handlers.run.TOOL_ALIASES", {"brutus": {
                 "capability": "brutus",
                 "agent": None,
                 "target_type": "asset",
                 "description": "Credential attacks",
                 "default_config": {},
             }}):
            h._cmd_use(["brutus"])
            h.console.lines.clear()
            h._cmd_set(["protocol", "ssh"])

        output = "\n".join(h.console.lines)
        # Must NOT contain an error about unknown/invalid
        assert "unknown" not in output.lower(), f"Valid enum value should be accepted. Got:\n{output}"
        assert "invalid" not in output.lower(), f"Valid enum value should be accepted. Got:\n{output}"
