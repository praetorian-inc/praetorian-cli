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


def test_complete_recording_flow():
    """Test writing header and events to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "session.cast"
        metadata = {
            "agent_name": "test-agent",
            "user": "testuser"
        }

        writer = AsciinemaWriter(filepath, width=80, height=24, metadata=metadata)

        # Start recording
        assert writer.start() is True
        assert filepath.exists()

        # Write some events
        writer.write_event(b"$ ls -la\r\n")
        writer.write_event(b"total 48\r\n")
        writer.write_event(b"drwxr-xr-x 5 user group 160 Jan 12 14:20 .\r\n")

        # Close recording
        writer.close()

        # Verify file contents
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # First line should be header
        header = json.loads(lines[0])
        assert header["version"] == 2
        assert header["agent_name"] == "test-agent"

        # Subsequent lines should be events
        assert len(lines) >= 4  # Header + 3 events

        event1 = json.loads(lines[1])
        assert len(event1) == 3  # [timestamp, event_type, data]
        assert event1[1] == "o"  # Output event
        assert "$ ls -la" in event1[2]


def test_invalid_utf8_handling():
    """Test that invalid UTF-8 bytes are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.cast"
        metadata = {"agent_name": "test"}

        writer = AsciinemaWriter(filepath, width=80, height=24, metadata=metadata)
        writer.start()

        # Write invalid UTF-8 bytes
        writer.write_event(b'\xff\xfe\x00\x00')
        writer.close()

        # Verify file was written (bytes replaced with U+FFFD)
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # Should have header + 1 event
        assert len(lines) >= 2
        event = json.loads(lines[1])
        # Invalid bytes should be replaced, not cause exception
        assert event[1] == "o"
        assert isinstance(event[2], str)  # Successfully decoded as string
