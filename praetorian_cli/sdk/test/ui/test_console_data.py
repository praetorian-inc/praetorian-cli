import json
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
