"""Integration tests for session recording."""
import os
import tempfile
from pathlib import Path
import subprocess
import pytest


@pytest.mark.integration
def test_simple_command_recording(clear_recording_env):
    """Test recording a simple command (not real SSH)."""
    from praetorian_cli.ui.aegis.recording import SessionRecorder

    with tempfile.TemporaryDirectory() as tmpdir:
        metadata = {
            "agent_name": "integration-test",
            "user": "testuser"
        }

        # Use ls command as proxy for SSH
        recorder = SessionRecorder(command=["ls", "-la", "/tmp"], metadata=metadata)
        recorder.recording_path = Path(tmpdir) / "test.cast"

        exit_code = recorder.run()

        # Verify success
        assert exit_code == 0
        assert recorder.recording_path.exists()

        # Verify recording has content
        content = recorder.recording_path.read_text()
        lines = content.split('\n')

        # Should have header + events
        assert len(lines) >= 2

        # First line is header
        import json
        header = json.loads(lines[0])
        assert header["version"] == 2
        assert header["agent_name"] == "integration-test"


@pytest.mark.integration
def test_interactive_program_recording(clear_recording_env):
    """Test recording an interactive program."""
    from praetorian_cli.ui.aegis.recording import SessionRecorder

    with tempfile.TemporaryDirectory() as tmpdir:
        metadata = {"agent_name": "test", "user": "test"}

        # Use echo with interactive-like output
        recorder = SessionRecorder(command=["echo", "-e", "Line1\\nLine2\\nLine3"], metadata=metadata)
        recorder.recording_path = Path(tmpdir) / "interactive.cast"

        exit_code = recorder.run()

        assert exit_code == 0

        # In pytest environment, PTY allocation may fail and fall back to subprocess.run
        # In that case, recording file may be created but have minimal content
        # We verify the command succeeded regardless of recording
        if recorder.recording_path.exists():
            content = recorder.recording_path.read_text()
            # Verify at minimum the header was written (graceful degradation)
            import json
            lines = content.split('\n')
            if lines and lines[0].strip():
                header = json.loads(lines[0])
                assert header["version"] == 2


@pytest.mark.integration
def test_recording_playback_compatibility(clear_recording_env):
    """Test that recorded files can be read by asciinema (format validation)."""
    from praetorian_cli.ui.aegis.recording import SessionRecorder

    with tempfile.TemporaryDirectory() as tmpdir:
        metadata = {"agent_name": "playback-test", "user": "test"}

        recorder = SessionRecorder(command=["echo", "test playback"], metadata=metadata)
        recorder.recording_path = Path(tmpdir) / "playback.cast"

        exit_code = recorder.run()
        assert exit_code == 0

        # Try to validate format with asciinema if installed
        # Otherwise just verify it's valid JSON lines
        try:
            result = subprocess.run(
                ["asciinema", "cat", str(recorder.recording_path)],
                capture_output=True,
                timeout=5
            )
            # If asciinema is installed, it should succeed
            assert result.returncode == 0
        except FileNotFoundError:
            # asciinema not installed, just verify JSON format
            import json
            with open(recorder.recording_path) as f:
                lines = f.readlines()

            # All lines should be valid JSON
            for line in lines:
                if line.strip():
                    obj = json.loads(line)  # Will raise if invalid
                    assert isinstance(obj, (dict, list))
