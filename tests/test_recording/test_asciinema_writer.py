"""Tests for Asciicast v2 writer."""
import json
import tempfile
from pathlib import Path
import pytest
from praetorian_cli.ui.aegis.recording.asciinema_writer import AsciinemaWriter


def test_header_generation():
    """Test Asciicast v2 header format with custom metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.cast"
        metadata = {
            "agent_name": "test-agent",
            "agent_id": "C.test-123",
            "user": "test@example.com",
            "title": "Test Session"
        }

        writer = AsciinemaWriter(
            filepath=filepath,
            width=80,
            height=24,
            metadata=metadata
        )

        # Check header structure before writing
        assert writer.header["version"] == 2
        assert writer.header["width"] == 80
        assert writer.header["height"] == 24
        assert writer.header["agent_name"] == "test-agent"
        assert writer.header["agent_id"] == "C.test-123"
        assert writer.header["user"] == "test@example.com"
        assert writer.header["title"] == "Test Session"
