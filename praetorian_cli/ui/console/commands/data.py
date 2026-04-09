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

    def _cmd_import(self, args):
        """Import scanner data or bulk-create entities from CSV/JSON."""
        if len(args) < 2:
            self.console.print('[dim]Usage: import <type> <file_path>[/dim]')
            self.console.print(f'[dim]  Scanners: {", ".join(sorted(VALID_SCANNERS))}[/dim]')
            self.console.print(f'[dim]  Entities: {", ".join(sorted(VALID_ENTITY_TYPES))}[/dim]')
            return

        import_type = args[0].lower()
        file_path = args[1]

        if import_type not in VALID_SCANNERS and import_type not in VALID_ENTITY_TYPES:
            valid = sorted(VALID_SCANNERS | VALID_ENTITY_TYPES)
            self.console.print(f'[error]Unknown import type: {import_type}. Valid types: {", ".join(valid)}[/error]')
            return

        if not os.path.isfile(file_path):
            self.console.print(f'[error]File does not exist: {file_path}[/error]')
            return

        if import_type in VALID_SCANNERS:
            self._import_scanner(import_type, file_path)
        else:
            self._import_entities(import_type, file_path)

    def _import_scanner(self, scanner, file_path):
        """Import vulnerability scanner data."""
        try:
            self.sdk.integrations.add_import_integration(f'{scanner}-import', file_path)
            self.console.print(f'[success]Imported {scanner} data from {os.path.basename(file_path)}[/success]')
        except Exception as e:
            self.console.print(f'[error]Import failed: {e}[/error]')

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
