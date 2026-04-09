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
