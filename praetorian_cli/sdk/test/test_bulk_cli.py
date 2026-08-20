import json
import click
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.bulk import _read_records, _validate_required_keys


def _invoke(runner, sdk, argv, **kwargs):
    """Invoke the CLI with a patched SDK factory.

    The `chariot` click group replaces `ctx.obj` with a `Chariot` instance,
    built lazily inside the group callback via `from praetorian_cli.sdk.chariot
    import Chariot`. We patch that source symbol so every instantiation yields
    our fake SDK. We also seed `ctx.obj` with the dict shape the group expects
    (`{'keychain', 'proxy'}`) so invocation doesn't blow up before the patch
    takes effect. (Mirrors the pattern used in test_schedule_cli.py.)
    """
    obj = {'keychain': MagicMock(), 'proxy': ''}
    chariot.is_debug = False
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        return runner.invoke(chariot, argv, obj=obj, **kwargs)


class TestReadRecords:

    def test_json_array_file(self, tmp_path):
        f = tmp_path / 'data.json'
        f.write_text(json.dumps([{'group': 'a', 'identifier': 'b'}]))
        result = _read_records(str(f))
        assert result == [{'group': 'a', 'identifier': 'b'}]

    def test_jsonl_file(self, tmp_path):
        f = tmp_path / 'data.jsonl'
        f.write_text('{"group":"a","identifier":"b"}\n{"group":"c","identifier":"d"}\n')
        result = _read_records(str(f))
        assert len(result) == 2
        assert result[0]['group'] == 'a'
        assert result[1]['group'] == 'c'

    def test_empty_file_errors(self, tmp_path):
        f = tmp_path / 'empty.json'
        f.write_text('')
        with pytest.raises(click.ClickException):
            _read_records(str(f))

    def test_invalid_json_errors(self, tmp_path):
        f = tmp_path / 'bad.json'
        f.write_text('not json at all')
        with pytest.raises(click.ClickException):
            _read_records(str(f))

    def test_file_not_found_errors(self):
        with pytest.raises(click.ClickException):
            _read_records('/nonexistent/path/file.json')

    def test_stdin(self, monkeypatch):
        import io
        monkeypatch.setattr('sys.stdin', io.StringIO('[{"group":"x","identifier":"y"}]'))
        result = _read_records('-')
        assert result == [{'group': 'x', 'identifier': 'y'}]

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / 'data.jsonl'
        f.write_text('\n{"group":"a","identifier":"b"}\n\n{"group":"c","identifier":"d"}\n\n')
        result = _read_records(str(f))
        assert len(result) == 2


class TestValidateRequiredKeys:

    def test_valid_records(self):
        records = [{'group': 'a', 'identifier': 'b'}]
        _validate_required_keys(records, ['group', 'identifier'], 'Asset')

    def test_missing_key_errors(self):
        records = [{'group': 'a'}]
        with pytest.raises(click.ClickException):
            _validate_required_keys(records, ['group', 'identifier'], 'Asset')


class TestBulkAddAssetCli:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()
        self.sdk.assets.bulk_add.return_value = {'job': 'j1'}

    def test_bulk_add_asset_from_file(self, tmp_path):
        f = tmp_path / 'assets.json'
        records = [{'group': 'example.com', 'identifier': '1.2.3.4'}]
        f.write_text(json.dumps(records))

        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'asset', '--file', str(f),
        ])
        assert result.exit_code == 0
        self.sdk.assets.bulk_add.assert_called_once_with(records)
        assert 'j1' in result.output

    def test_bulk_add_asset_from_stdin(self):
        records = [{'group': 'test.com', 'identifier': '10.0.0.1'}]
        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'asset', '--file', '-',
        ], input=json.dumps(records))
        assert result.exit_code == 0
        self.sdk.assets.bulk_add.assert_called_once()

    def test_bulk_add_asset_missing_field(self, tmp_path):
        f = tmp_path / 'bad.json'
        f.write_text(json.dumps([{'group': 'example.com'}]))
        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'asset', '--file', str(f),
        ])
        assert 'ERROR' in result.output or result.exit_code != 0
        self.sdk.assets.bulk_add.assert_not_called()

    def test_bulk_add_asset_invalid_json(self, tmp_path):
        f = tmp_path / 'bad.json'
        f.write_text('not json')
        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'asset', '--file', str(f),
        ])
        assert 'ERROR' in result.output or result.exit_code != 0
        self.sdk.assets.bulk_add.assert_not_called()


class TestBulkAddRiskCli:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()
        self.sdk.risks.bulk_add.return_value = {'job': 'j2'}

    def test_bulk_add_risk_from_file(self, tmp_path):
        f = tmp_path / 'risks.json'
        records = [{'asset_key': '#asset#x#x', 'name': 'CVE-2024-1', 'status': 'O'}]
        f.write_text(json.dumps(records))

        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'risk', '--file', str(f),
        ])
        assert result.exit_code == 0
        self.sdk.risks.bulk_add.assert_called_once_with(records)

    def test_bulk_add_risk_missing_status(self, tmp_path):
        f = tmp_path / 'bad.json'
        f.write_text(json.dumps([{'asset_key': '#a#b#c', 'name': 'x'}]))
        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'risk', '--file', str(f),
        ])
        assert 'ERROR' in result.output or result.exit_code != 0
        self.sdk.risks.bulk_add.assert_not_called()


class TestBulkAddAttributeCli:

    def setup_method(self):
        self.runner = CliRunner()
        self.sdk = MagicMock()
        self.sdk.attributes.bulk_add.return_value = {'job': 'j3'}

    def test_bulk_add_attribute_from_file(self, tmp_path):
        f = tmp_path / 'attrs.json'
        records = [{'source_key': '#asset#x#x', 'name': 'port', 'value': '443'}]
        f.write_text(json.dumps(records))

        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'attribute', '--file', str(f),
        ])
        assert result.exit_code == 0
        self.sdk.attributes.bulk_add.assert_called_once_with(records)

    def test_bulk_add_attribute_from_stdin(self):
        records = [{'source_key': '#asset#x#x', 'name': 'port', 'value': '443'}]
        result = _invoke(self.runner, self.sdk, [
            'bulk', 'add', 'attribute', '--file', '-',
        ], input=json.dumps(records))
        assert result.exit_code == 0
        self.sdk.attributes.bulk_add.assert_called_once()
