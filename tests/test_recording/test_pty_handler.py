"""Tests for PTY handler."""
import os
import subprocess
import pytest
from praetorian_cli.ui.aegis.recording.pty_handler import PTYHandler


def test_pty_allocation():
    """Test that PTY pair is created successfully."""
    handler = PTYHandler(command=["echo", "test"])

    master_fd, process = handler.spawn()

    try:
        # Verify master FD is valid
        assert master_fd > 0
        assert isinstance(master_fd, int)

        # Verify process started
        assert process.pid > 0

        # Wait for process to complete
        process.wait(timeout=1.0)
        assert process.returncode == 0
    finally:
        # Cleanup
        if master_fd:
            os.close(master_fd)


def test_pty_data_flow():
    """Test that data flows through PTY correctly."""
    handler = PTYHandler(command=["echo", "hello world"])

    master_fd, process = handler.spawn()

    try:
        # Read output from master PTY
        import select
        readable, _, _ = select.select([master_fd], [], [], 1.0)

        if readable:
            output = os.read(master_fd, 4096)
            # Output should contain our echo text
            assert b"hello world" in output

        process.wait(timeout=1.0)
        assert process.returncode == 0
    finally:
        os.close(master_fd)
