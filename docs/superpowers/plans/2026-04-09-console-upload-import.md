# Console Upload & Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `upload` and `import` commands to the Guard Console so operators can upload files, import scanner data, and bulk-create seeds/assets/risks from CSV/JSON without leaving the interactive shell.

**Architecture:** All SDK methods already exist (`sdk.files.add`, `sdk.integrations.add_import_integration`, `sdk.seeds.add`, `sdk.assets.add`, `sdk.risks.add`). We add a new `DataCommands` mixin class with `_cmd_upload` and `_cmd_import` handlers, a `_parse_import_file` helper for CSV/JSON parsing, and wire them into the console dispatch table, completer, and help text.

**Tech Stack:** Python, Click (CLI), prompt_toolkit + Rich (console UI), csv/json stdlib modules

---

### File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `praetorian_cli/ui/console/commands/data.py` | `DataCommands` mixin: `_cmd_upload`, `_cmd_import`, `_parse_import_file` |
| Modify | `praetorian_cli/ui/console/commands/__init__.py` | Export `DataCommands` |
| Modify | `praetorian_cli/ui/console/console.py` | Mix in `DataCommands`, add to dispatch table, completer, and help |
| Create | `praetorian_cli/sdk/test/ui/test_console_data.py` | Unit tests for `DataCommands` |

---

### Task 1: Create `DataCommands` mixin with `_cmd_upload`

**Files:**
- Create: `praetorian_cli/ui/console/commands/data.py`
- Create: `praetorian_cli/sdk/test/ui/test_console_data.py`

- [ ] **Step 1: Write the failing test for `_cmd_upload`**

Create `praetorian_cli/sdk/test/ui/test_console_data.py`:

```python
import os
import tempfile
import pytest

from praetorian_cli.sdk.test.ui_mocks import MockConsole


class MockFiles:
    def __init__(self):
        self.calls = []

    def add(self, local_path, name=None):
        self.calls.append({'method': 'add', 'local_path': local_path, 'name': name})


class MockIntegrations:
    def __init__(self):
        self.calls = []

    def add_import_integration(self, name, local_filepath):
        self.calls.append({'method': 'add_import_integration', 'name': name, 'local_filepath': local_filepath})


class MockSeeds:
    def __init__(self):
        self.calls = []

    def add(self, status='P', seed_type='asset', **kwargs):
        self.calls.append({'method': 'add', 'status': status, 'seed_type': seed_type, **kwargs})
        return {'key': f'#asset#{kwargs.get("dns", "test")}'}


class MockAssets:
    def __init__(self):
        self.calls = []

    def add(self, group, identifier, type='asset', status='A', surface='', resource_type=''):
        self.calls.append({
            'method': 'add', 'group': group, 'identifier': identifier,
            'type': type, 'status': status, 'surface': surface,
        })
        return {'key': f'#asset#{group}#{identifier}'}


class MockRisks:
    def __init__(self):
        self.calls = []

    def add(self, asset_key, name, status, comment=None, capability='', title=None, tags=None):
        self.calls.append({
            'method': 'add', 'asset_key': asset_key, 'name': name,
            'status': status, 'comment': comment, 'title': title, 'tags': tags,
        })
        return {'key': f'#risk#{name}'}


class MockDataSDK:
    def __init__(self):
        self.files = MockFiles()
        self.integrations = MockIntegrations()
        self.seeds = MockSeeds()
        self.assets = MockAssets()
        self.risks = MockRisks()


def make_data_commands():
    """Build a DataCommands instance wired to mocks."""
    from praetorian_cli.ui.console.commands.data import DataCommands

    class TestableDataCommands(DataCommands):
        pass

    obj = TestableDataCommands()
    obj.sdk = MockDataSDK()
    obj.console = MockConsole()
    obj.colors = {
        'primary': 'cyan', 'accent': 'magenta', 'dim': 'dim',
        'success': 'green', 'warning': 'yellow', 'error': 'red',
        'info': 'blue',
    }
    return obj


class TestUploadCommand:

    def test_upload_no_args_shows_usage(self):
        cmd = make_data_commands()
        cmd._cmd_upload([])
        assert any('Usage' in line for line in cmd.console.lines)

    def test_upload_missing_file_shows_error(self):
        cmd = make_data_commands()
        cmd._cmd_upload(['/nonexistent/file.txt'])
        assert any('not found' in line.lower() or 'does not exist' in line.lower() for line in cmd.console.lines)

    def test_upload_success(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'hello')
            tmp_path = f.name
        try:
            cmd._cmd_upload([tmp_path])
            assert len(cmd.sdk.files.calls) == 1
            assert cmd.sdk.files.calls[0]['local_path'] == tmp_path
            assert cmd.sdk.files.calls[0]['name'] is None
            assert any('upload' in line.lower() for line in cmd.console.lines)
        finally:
            os.unlink(tmp_path)

    def test_upload_with_name(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'hello')
            tmp_path = f.name
        try:
            cmd._cmd_upload([tmp_path, '--name', 'home/custom.txt'])
            assert cmd.sdk.files.calls[0]['name'] == 'home/custom.txt'
        finally:
            os.unlink(tmp_path)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestUploadCommand -v 2>&1 | head -30`

Expected: FAIL with `ModuleNotFoundError` (data.py doesn't exist yet)

- [ ] **Step 3: Write the `DataCommands` mixin with `_cmd_upload`**

Create `praetorian_cli/ui/console/commands/data.py`:

```python
"""Upload and import commands. Mixed into GuardConsole."""

import csv
import io
import json
import os


VALID_SCANNERS = {'insightvm', 'qualys', 'nessus'}
VALID_ENTITY_TYPES = {'seeds', 'assets', 'risks'}


class DataCommands:
    """File upload, scanner import, and bulk entity import. Mixed into GuardConsole."""

    def _cmd_upload(self, args):
        """Upload a local file to Guard storage."""
        if not args:
            self.console.print('[dim]Usage: upload <local_path> [--name <guard_name>][/dim]')
            return

        local_path = args[0]
        name = None
        for i, a in enumerate(args):
            if a == '--name' and i + 1 < len(args):
                name = args[i + 1]

        if not os.path.isfile(local_path):
            self.console.print(f'[error]File does not exist: {local_path}[/error]')
            return

        try:
            self.sdk.files.add(local_path, name)
            display_name = name or os.path.basename(local_path)
            self.console.print(f'[success]Uploaded: {display_name}[/success]')
        except Exception as e:
            self.console.print(f'[error]Upload failed: {e}[/error]')
```

- [ ] **Step 4: Run the upload tests to verify they pass**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestUploadCommand -v`

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/ui/console/commands/data.py praetorian_cli/sdk/test/ui/test_console_data.py
git commit -m "feat: add upload command to guard console"
```

---

### Task 2: Add `_cmd_import` for scanner data

**Files:**
- Modify: `praetorian_cli/ui/console/commands/data.py`
- Modify: `praetorian_cli/sdk/test/ui/test_console_data.py`

- [ ] **Step 1: Write failing tests for scanner import**

Append to `praetorian_cli/sdk/test/ui/test_console_data.py`:

```python
class TestImportScannerCommand:

    def test_import_no_args_shows_usage(self):
        cmd = make_data_commands()
        cmd._cmd_import([])
        assert any('Usage' in line for line in cmd.console.lines)

    def test_import_scanner_missing_file_shows_error(self):
        cmd = make_data_commands()
        cmd._cmd_import(['nessus', '/nonexistent/file.nessus'])
        assert any('not found' in line.lower() or 'does not exist' in line.lower() for line in cmd.console.lines)

    def test_import_insightvm(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
            f.write(b'<xml/>')
            tmp_path = f.name
        try:
            cmd._cmd_import(['insightvm', tmp_path])
            assert len(cmd.sdk.integrations.calls) == 1
            call = cmd.sdk.integrations.calls[0]
            assert call['name'] == 'insightvm-import'
            assert call['local_filepath'] == tmp_path
            assert any('import' in line.lower() for line in cmd.console.lines)
        finally:
            os.unlink(tmp_path)

    def test_import_qualys(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            f.write(b'data')
            tmp_path = f.name
        try:
            cmd._cmd_import(['qualys', tmp_path])
            assert cmd.sdk.integrations.calls[0]['name'] == 'qualys-import'
        finally:
            os.unlink(tmp_path)

    def test_import_nessus(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.nessus', delete=False) as f:
            f.write(b'data')
            tmp_path = f.name
        try:
            cmd._cmd_import(['nessus', tmp_path])
            assert cmd.sdk.integrations.calls[0]['name'] == 'nessus-import'
        finally:
            os.unlink(tmp_path)

    def test_import_unknown_type_shows_error(self):
        cmd = make_data_commands()
        cmd._cmd_import(['bogus', '/tmp/file.csv'])
        assert any('unknown' in line.lower() or 'valid' in line.lower() for line in cmd.console.lines)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestImportScannerCommand -v 2>&1 | head -30`

Expected: FAIL with `AttributeError` (_cmd_import doesn't exist yet)

- [ ] **Step 3: Add `_cmd_import` to `DataCommands` with scanner support**

Append to the `DataCommands` class in `praetorian_cli/ui/console/commands/data.py`:

```python
    def _cmd_import(self, args):
        """Import scanner data or bulk-create entities from CSV/JSON."""
        if len(args) < 2:
            self.console.print('[dim]Usage: import <type> <file_path>[/dim]')
            self.console.print(f'[dim]  Scanners: {", ".join(sorted(VALID_SCANNERS))}[/dim]')
            self.console.print(f'[dim]  Entities: {", ".join(sorted(VALID_ENTITY_TYPES))}[/dim]')
            return

        import_type = args[0].lower()
        file_path = args[1]

        if not os.path.isfile(file_path):
            self.console.print(f'[error]File does not exist: {file_path}[/error]')
            return

        if import_type in VALID_SCANNERS:
            self._import_scanner(import_type, file_path)
        elif import_type in VALID_ENTITY_TYPES:
            self._import_entities(import_type, file_path)
        else:
            valid = sorted(VALID_SCANNERS | VALID_ENTITY_TYPES)
            self.console.print(f'[error]Unknown import type: {import_type}. Valid types: {", ".join(valid)}[/error]')

    def _import_scanner(self, scanner, file_path):
        """Import vulnerability scanner data."""
        try:
            self.sdk.integrations.add_import_integration(f'{scanner}-import', file_path)
            self.console.print(f'[success]Imported {scanner} data from {os.path.basename(file_path)}[/success]')
        except Exception as e:
            self.console.print(f'[error]Import failed: {e}[/error]')
```

- [ ] **Step 4: Run the scanner import tests to verify they pass**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestImportScannerCommand -v`

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add praetorian_cli/ui/console/commands/data.py praetorian_cli/sdk/test/ui/test_console_data.py
git commit -m "feat: add scanner import command to guard console"
```

---

### Task 3: Add CSV/JSON parsing and entity import (seeds, assets, risks)

**Files:**
- Modify: `praetorian_cli/ui/console/commands/data.py`
- Modify: `praetorian_cli/sdk/test/ui/test_console_data.py`

- [ ] **Step 1: Write failing tests for entity import**

Append to `praetorian_cli/sdk/test/ui/test_console_data.py`:

```python
class TestImportEntitiesCommand:

    def test_import_seeds_csv(self):
        cmd = make_data_commands()
        csv_content = "dns,type,status\nexample.com,asset,A\ntest.org,asset,P\n"
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name
        try:
            cmd._cmd_import(['seeds', tmp_path])
            assert len(cmd.sdk.seeds.calls) == 2
            assert cmd.sdk.seeds.calls[0]['dns'] == 'example.com'
            assert cmd.sdk.seeds.calls[0]['seed_type'] == 'asset'
            assert cmd.sdk.seeds.calls[0]['status'] == 'A'
            assert cmd.sdk.seeds.calls[1]['dns'] == 'test.org'
            assert any('2' in line and 'success' in line.lower() or 'added' in line.lower() for line in cmd.console.lines)
        finally:
            os.unlink(tmp_path)

    def test_import_seeds_json(self):
        cmd = make_data_commands()
        records = [
            {"dns": "example.com", "type": "asset", "status": "A"},
            {"dns": "test.org", "type": "asset", "status": "P"},
        ]
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            json.dump(records, f)
            tmp_path = f.name
        try:
            cmd._cmd_import(['seeds', tmp_path])
            assert len(cmd.sdk.seeds.calls) == 2
        finally:
            os.unlink(tmp_path)

    def test_import_assets_csv(self):
        cmd = make_data_commands()
        csv_content = "group,identifier,type,status,surface\nexample.com,1.2.3.4,asset,A,external\n"
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name
        try:
            cmd._cmd_import(['assets', tmp_path])
            assert len(cmd.sdk.assets.calls) == 1
            call = cmd.sdk.assets.calls[0]
            assert call['group'] == 'example.com'
            assert call['identifier'] == '1.2.3.4'
            assert call['type'] == 'asset'
            assert call['status'] == 'A'
            assert call['surface'] == 'external'
        finally:
            os.unlink(tmp_path)

    def test_import_risks_csv(self):
        cmd = make_data_commands()
        csv_content = 'asset,name,status,comment,title\n"#asset#example.com#1.2.3.4",CVE-2024-1234,TI,test comment,Test Title\n'
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name
        try:
            cmd._cmd_import(['risks', tmp_path])
            assert len(cmd.sdk.risks.calls) == 1
            call = cmd.sdk.risks.calls[0]
            assert call['asset_key'] == '#asset#example.com#1.2.3.4'
            assert call['name'] == 'CVE-2024-1234'
            assert call['status'] == 'TI'
            assert call['comment'] == 'test comment'
            assert call['title'] == 'Test Title'
        finally:
            os.unlink(tmp_path)

    def test_import_risks_with_tags_json(self):
        cmd = make_data_commands()
        records = [{
            "asset": "#asset#example.com#1.2.3.4",
            "name": "CVE-2024-1234",
            "status": "TI",
            "tags": ["critical", "needs-review"],
        }]
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            json.dump(records, f)
            tmp_path = f.name
        try:
            cmd._cmd_import(['risks', tmp_path])
            assert cmd.sdk.risks.calls[0]['tags'] == ['critical', 'needs-review']
        finally:
            os.unlink(tmp_path)

    def test_import_unsupported_extension_shows_error(self):
        cmd = make_data_commands()
        with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as f:
            f.write('<xml/>')
            tmp_path = f.name
        try:
            cmd._cmd_import(['seeds', tmp_path])
            assert any('csv' in line.lower() or 'json' in line.lower() for line in cmd.console.lines)
        finally:
            os.unlink(tmp_path)

    def test_import_partial_failure_reports_count(self):
        """If some rows fail, the summary should show both successes and errors."""
        cmd = make_data_commands()
        # Make the mock raise on the second call
        original_add = cmd.sdk.seeds.add
        call_count = [0]
        def failing_add(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception('simulated failure')
            return original_add(**kwargs)
        cmd.sdk.seeds.add = failing_add

        csv_content = "dns,type,status\nexample.com,asset,A\nfail.com,asset,A\ngood.org,asset,A\n"
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name
        try:
            cmd._cmd_import(['seeds', tmp_path])
            output = ' '.join(cmd.console.lines)
            assert '2' in output  # 2 successes
            assert '1' in output  # 1 error
        finally:
            os.unlink(tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestImportEntitiesCommand -v 2>&1 | head -30`

Expected: FAIL with `AttributeError` (_import_entities doesn't exist yet)

- [ ] **Step 3: Add `_parse_import_file` and `_import_entities` to `DataCommands`**

Append to the `DataCommands` class in `praetorian_cli/ui/console/commands/data.py`:

```python
    def _parse_import_file(self, file_path):
        """Parse a CSV or JSON file into a list of dicts. Returns (records, error_msg)."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            try:
                with open(file_path, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    return list(reader), None
            except Exception as e:
                return None, f'Failed to parse CSV: {e}'

        elif ext == '.json':
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    return None, 'JSON file must contain an array of objects'
                return data, None
            except Exception as e:
                return None, f'Failed to parse JSON: {e}'

        else:
            return None, f'Unsupported file format: {ext}. Use .csv or .json'

    def _import_entities(self, entity_type, file_path):
        """Bulk-create entities from CSV/JSON."""
        records, err = self._parse_import_file(file_path)
        if err:
            self.console.print(f'[error]{err}[/error]')
            return

        if not records:
            self.console.print('[dim]No records found in file.[/dim]')
            return

        added = 0
        errors = 0

        for i, row in enumerate(records, 1):
            try:
                if entity_type == 'seeds':
                    self._import_seed(row)
                elif entity_type == 'assets':
                    self._import_asset(row)
                elif entity_type == 'risks':
                    self._import_risk(row)
                added += 1
            except Exception as e:
                errors += 1
                self.console.print(f'[error]Row {i}: {e}[/error]')

        status = 'success' if errors == 0 else 'warning'
        self.console.print(f'[{status}]Added {added}/{added + errors} {entity_type}. {errors} errors.[/{status}]')

    def _import_seed(self, row):
        """Create a single seed from a row dict."""
        seed_type = row.get('type', 'asset')
        status = row.get('status', 'P')
        # Pass remaining fields as kwargs (dns, name, etc.)
        kwargs = {k: v for k, v in row.items() if k not in ('type', 'status')}
        self.sdk.seeds.add(status=status, seed_type=seed_type, **kwargs)

    def _import_asset(self, row):
        """Create a single asset from a row dict."""
        group = row.get('group', '')
        identifier = row.get('identifier', group)
        asset_type = row.get('type', 'asset')
        status = row.get('status', 'A')
        surface = row.get('surface', '')
        resource_type = row.get('resource_type', '')
        if not group:
            raise ValueError('Missing required field: group')
        self.sdk.assets.add(group, identifier, asset_type, status, surface, resource_type=resource_type)

    def _import_risk(self, row):
        """Create a single risk from a row dict."""
        asset_key = row.get('asset', '')
        name = row.get('name', '')
        status = row.get('status', '')
        if not asset_key or not name or not status:
            raise ValueError('Missing required field(s): asset, name, status')
        comment = row.get('comment') or None
        title = row.get('title') or None
        tags = row.get('tags')
        # CSV tags come as comma-separated string; JSON as list
        if isinstance(tags, str) and tags:
            tags = [t.strip() for t in tags.split(',')]
        elif not tags:
            tags = None
        self.sdk.risks.add(asset_key, name, status, comment=comment, title=title, tags=tags)
```

- [ ] **Step 4: Run all entity import tests to verify they pass**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py::TestImportEntitiesCommand -v`

Expected: All 7 tests PASS

- [ ] **Step 5: Run the full test file to verify nothing is broken**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py -v`

Expected: All 16 tests PASS (4 upload + 5 scanner + 7 entity)

- [ ] **Step 6: Commit**

```bash
git add praetorian_cli/ui/console/commands/data.py praetorian_cli/sdk/test/ui/test_console_data.py
git commit -m "feat: add bulk entity import (seeds/assets/risks) from CSV/JSON"
```

---

### Task 4: Wire `DataCommands` into the Guard Console

**Files:**
- Modify: `praetorian_cli/ui/console/commands/__init__.py`
- Modify: `praetorian_cli/ui/console/console.py`

- [ ] **Step 1: Export `DataCommands` from the commands package**

In `praetorian_cli/ui/console/commands/__init__.py`, add to existing imports:

```python
from praetorian_cli.ui.console.commands.data import DataCommands
```

- [ ] **Step 2: Mix `DataCommands` into `GuardConsole`**

In `praetorian_cli/ui/console/console.py`, update the class definition. Find:

```python
class GuardConsole(
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
    RendererMixin,
):
```

Replace with:

```python
class GuardConsole(
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
    DataCommands,
    RendererMixin,
):
```

- [ ] **Step 3: Add to the imports at the top of `console.py`**

In `praetorian_cli/ui/console/console.py`, find:

```python
from praetorian_cli.ui.console.commands import (
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
)
```

Replace with:

```python
from praetorian_cli.ui.console.commands import (
    ContextCommands,
    AccountCommands,
    SearchCommands,
    ToolCommands,
    MarcusCommands,
    ReportingCommands,
    DataCommands,
)
```

- [ ] **Step 4: Add `upload` and `import` to `CONSOLE_COMMANDS` completer list**

In `praetorian_cli/ui/console/console.py`, find the `CONSOLE_COMMANDS` list and add `'upload'` and `'import'` entries. Specifically, find:

```python
    'aegis',
    'configure', 'login',
```

Add before it:

```python
    'upload', 'import',
```

- [ ] **Step 5: Add to the dispatch table**

In `praetorian_cli/ui/console/console.py`, in the `_dispatch` method's `handlers` dict, find:

```python
            'aegis': self._cmd_aegis,
```

Add before it:

```python
            'upload': self._cmd_upload,
            'import': self._cmd_import,
```

- [ ] **Step 6: Add to the help table**

In `praetorian_cli/ui/console/console.py`, in the `_cmd_help` method, find:

```python
        help_table.add_row('', '')
        help_table.add_row('[section]Other[/section]', '')
```

Add before it:

```python
        help_table.add_row('', '')
        help_table.add_row('[section]Upload & Import[/section]', '')
        help_table.add_row('upload <path> [--name <name>]', 'Upload a file to Guard storage')
        help_table.add_row('import insightvm <file>', 'Import Rapid7 InsightVM XML data')
        help_table.add_row('import qualys <file>', 'Import Qualys VMDR CSV data')
        help_table.add_row('import nessus <file>', 'Import Tenable Nessus data')
        help_table.add_row('import seeds <csv|json>', 'Bulk-add seeds from file')
        help_table.add_row('import assets <csv|json>', 'Bulk-add assets from file')
        help_table.add_row('import risks <csv|json>', 'Bulk-add risks from file')
```

- [ ] **Step 7: Run the full test suite to verify nothing is broken**

Run: `cd /Users/ajman/Documents/Tools/praetorian-cli && python -m pytest praetorian_cli/sdk/test/ui/test_console_data.py -v`

Expected: All 16 tests PASS

- [ ] **Step 8: Commit**

```bash
git add praetorian_cli/ui/console/commands/__init__.py praetorian_cli/ui/console/console.py
git commit -m "feat: wire upload and import commands into guard console"
```
