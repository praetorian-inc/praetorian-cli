import json
import os
import tempfile
import textwrap
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.configure import configure


class TestConfigureGroup:

    def test_configure_is_a_group(self):
        """configure must be a Click group so subcommands can be added."""
        import click
        assert isinstance(configure, click.Group)

    def test_configure_has_credential_subcommand(self):
        assert 'credential' in configure.commands
