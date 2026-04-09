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
