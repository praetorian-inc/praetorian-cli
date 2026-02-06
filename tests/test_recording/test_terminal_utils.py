"""Tests for terminal utilities."""
import os
import pytest
from unittest.mock import patch
from praetorian_cli.ui.aegis.recording.terminal_utils import get_terminal_size_safe


def test_get_terminal_size_safe_with_tty():
    """Test that get_terminal_size_safe returns actual terminal size when available."""
    # Mock os.get_terminal_size to return a specific size
    with patch('os.get_terminal_size') as mock_term_size:
        mock_term_size.return_value = os.terminal_size((120, 40))

        width, height = get_terminal_size_safe()

        assert width == 120
        assert height == 40
        mock_term_size.assert_called_once()


def test_get_terminal_size_safe_without_tty():
    """Test that get_terminal_size_safe returns defaults when no TTY available."""
    # Mock os.get_terminal_size to raise OSError (no TTY)
    with patch('os.get_terminal_size', side_effect=OSError("not a tty")):
        width, height = get_terminal_size_safe()

        # Should fall back to defaults
        assert width == 80
        assert height == 24


def test_get_terminal_size_safe_returns_tuple():
    """Test that get_terminal_size_safe always returns a tuple of two integers."""
    width, height = get_terminal_size_safe()

    assert isinstance(width, int)
    assert isinstance(height, int)
    assert width > 0
    assert height > 0
