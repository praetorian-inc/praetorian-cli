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
