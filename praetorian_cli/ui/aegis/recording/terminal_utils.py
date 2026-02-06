"""Terminal utility functions for session recording."""
import os
from typing import Tuple


def get_terminal_size_safe() -> Tuple[int, int]:
    """
    Get terminal size with fallback to defaults for non-TTY environments.

    Returns:
        Tuple[int, int]: (width, height) in columns and rows.
                        Defaults to (80, 24) if terminal size unavailable.
    """
    try:
        term_size = os.get_terminal_size()
        return term_size.columns, term_size.lines
    except OSError:
        # Not a TTY (e.g., CI environment, subprocess), use defaults
        return 80, 24
