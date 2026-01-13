"""Tests for session recorder orchestrator."""
import os
import tempfile
from pathlib import Path
import pytest
from praetorian_cli.ui.aegis.recording.session_recorder import SessionRecorder


def test_recording_path_generation():
    """Test that recording paths are generated correctly."""
    metadata = {
        "agent_name": "test-agent",
        "agent_id": "C.test-123",
        "user": "testuser"
    }

    recorder = SessionRecorder(command=["echo", "test"], metadata=metadata)

    # Path should contain date directory and agent name
    assert recorder.recording_path.parent.name.startswith("2026-01-")
    assert "test-agent" in recorder.recording_path.name
    assert recorder.recording_path.suffix == ".cast"


def test_opt_out_via_env_var():
    """Test that PRAETORIAN_NO_RECORD environment variable disables recording."""
    # Set opt-out env var
    os.environ["PRAETORIAN_NO_RECORD"] = "1"

    try:
        metadata = {"agent_name": "test"}
        recorder = SessionRecorder(command=["echo", "test"], metadata=metadata)

        # Run should use subprocess.run fallback, not create recording
        exit_code = recorder.run()

        # Should succeed but not create recording file
        assert exit_code == 0
        assert not recorder.recording_path.exists()
    finally:
        del os.environ["PRAETORIAN_NO_RECORD"]


def test_recording_file_created(clear_recording_env):
    """Test that recording file is created on successful run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metadata = {
            "agent_name": "test-agent",
            "user": "testuser"
        }

        # Use a simple command that completes quickly
        recorder = SessionRecorder(command=["echo", "hello"], metadata=metadata)

        # Override recording path to use temp directory
        recorder.recording_path = Path(tmpdir) / "test-session.cast"

        # Run recording
        exit_code = recorder.run()

        # Verify recording file was created
        assert exit_code == 0
        assert recorder.recording_path.exists()

        # Verify file has content (header at minimum)
        content = recorder.recording_path.read_text()
        assert len(content) > 0
        assert "version" in content  # Asciicast header


def test_recording_failure_fallback(clear_recording_env):
    """Test that SSH continues when recording fails."""
    from praetorian_cli.ui.aegis.recording import SessionRecorder
    from unittest.mock import patch

    metadata = {"agent_name": "test", "user": "test"}
    recorder = SessionRecorder(command=["echo", "test"], metadata=metadata)

    # Mock AsciinemaWriter.start() to return False (recording failure)
    with patch('praetorian_cli.ui.aegis.recording.asciinema_writer.AsciinemaWriter.start', return_value=False):
        exit_code = recorder.run()

    # Should fall back to subprocess.run and succeed
    assert exit_code == 0


def test_pty_allocation_failure_fallback(clear_recording_env):
    """Test fallback when PTY allocation fails."""
    from praetorian_cli.ui.aegis.recording import SessionRecorder
    from unittest.mock import patch

    metadata = {"agent_name": "test", "user": "test"}
    recorder = SessionRecorder(command=["echo", "test"], metadata=metadata)

    # Mock pty.openpty() to raise OSError
    with patch('pty.openpty', side_effect=OSError("PTY allocation failed")):
        exit_code = recorder.run()

    # Should fall back to subprocess.run and succeed
    assert exit_code == 0
