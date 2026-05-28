"""Unit tests for `guard module` CLI commands."""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.module  # registers `module` subcommand on chariot
from praetorian_cli.catalog import Capability
from praetorian_cli.handlers.chariot import chariot

pytestmark = pytest.mark.cli


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False)


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


SAMPLE_CAPS = [
    Capability.from_api({
        "Name": "brutus", "Title": "Brutus", "Category": ["credential"],
        "Surface": "external", "Target": ["port"],
        "Description": "Credential attacks across 20+ protocols",
        "Version": "v1.2.3", "Executor": "chariot",
        "Parameters": [
            {"Name": "protocol", "Type": "string", "Description": "Target protocol", "Required": False},
        ],
    }),
    Capability.from_api({
        "Name": "nuclei", "Title": "Nuclei", "Category": ["scanner"],
        "Surface": "external", "Target": ["asset"],
        "Description": "Vulnerability scanner",
        "Version": "v2.0.0", "Executor": "chariot", "Parameters": [],
    }),
]


def _invoke(runner, fake_sdk, argv):
    obj = {"keychain": MagicMock(), "proxy": ""}
    with patch("praetorian_cli.sdk.chariot.Chariot", return_value=fake_sdk), \
         patch("praetorian_cli.handlers.cli_decorators.upgrade_check", lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, catch_exceptions=False)


class TestModuleSearch:
    def test_search_no_args_lists_all(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS):
            result = _invoke(runner, fake_sdk, ["module", "search"])
        assert result.exit_code == 0
        assert "brutus" in result.output
        assert "nuclei" in result.output

    def test_search_with_query(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS):
            result = _invoke(runner, fake_sdk, ["module", "search", "credential"])
        assert result.exit_code == 0
        assert "brutus" in result.output

    def test_search_with_category_filter(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS):
            result = _invoke(runner, fake_sdk, ["module", "search", "--category", "scanner"])
        assert result.exit_code == 0
        assert "nuclei" in result.output

    def test_search_json_output(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS):
            result = _invoke(runner, fake_sdk, ["module", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("praetorian_cli.catalog.CapabilityCatalog.all")
    def test_module_search_json_uses_catalog(self, mock_all, runner, fake_sdk):
        mock_all.return_value = [Capability.from_api(
            {'Name': 'brutus', 'Title': 'Brutus', 'Category': ['credential'],
             'Surface': 'external', 'Target': ['port'], 'Description': 'creds',
             'Version': '0.2.0', 'Executor': 'chariot', 'Parameters': []})]
        with patch("praetorian_cli.runners.local.list_installed", return_value={}):
            result = _invoke(runner, fake_sdk, ["module", "search", "brutus", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "brutus"
        assert data[0]["version"] == "0.2.0"


class TestModuleInfo:
    def test_info_existing_module(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS), \
             patch("praetorian_cli.registry.ModuleRegistry.get_version", return_value=None):
            result = _invoke(runner, fake_sdk, ["module", "info", "brutus"])
        assert result.exit_code == 0
        assert "brutus" in result.output
        assert "credential" in result.output.lower() or "Credential" in result.output

    def test_info_unknown_module(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS):
            result = _invoke(runner, fake_sdk, ["module", "info", "nonexistent"])
        assert result.exit_code != 0

    def test_info_json_output(self, runner, fake_sdk):
        with patch("praetorian_cli.catalog.CapabilityCatalog.all", return_value=SAMPLE_CAPS), \
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
