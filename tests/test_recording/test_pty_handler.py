"""Tests for PTY handler."""
import os
import subprocess
import pytest
import struct
import fcntl
import termios
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


def test_pty_initial_window_size():
    """Test that PTY window size is set on creation."""
    handler = PTYHandler(command=["sleep", "0.1"])

    master_fd, process = handler.spawn()

    try:
        # Read PTY window size
        winsize = fcntl.ioctl(master_fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, xpixel, ypixel = struct.unpack("HHHH", winsize)

        # Window size should be set (not 0x0)
        # Either to current terminal size or default (24x80)
        assert rows > 0, f"PTY rows should be > 0, got {rows}"
        assert cols > 0, f"PTY columns should be > 0, got {cols}"

        # Verify it's reasonable (either terminal size or defaults)
        try:
            term_size = os.get_terminal_size()
            # Should match current terminal or be defaults (24x80)
            assert (rows == term_size.lines and cols == term_size.columns) or \
                   (rows == 24 and cols == 80), \
                   f"Expected terminal size ({term_size.lines}x{term_size.columns}) or defaults (24x80), got {rows}x{cols}"
        except OSError:
            # No terminal available (CI environment), check for defaults
            assert rows == 24 and cols == 80, \
                   f"Expected default size (24x80) when no terminal, got {rows}x{cols}"

        process.wait(timeout=1.0)
    finally:
        os.close(master_fd)
        if process.poll() is None:
            process.terminate()
            process.wait()
