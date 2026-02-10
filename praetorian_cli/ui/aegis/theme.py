#!/usr/bin/env python3
"""
Centralized color theme for the Aegis TUI.

All color constants and Rich style definitions live here so that every
module in the aegis UI package can import them from a single source of
truth.  When updating the palette, only this file needs to change.
"""

from rich.theme import Theme

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
PRIMARY_RED = "#e63948"       # CTAs, threats, high priority, errors
SECONDARY_BLUE = "#11C3DB"   # Links, info, headers, titles, selected items
COMPLEMENTARY_GOLD = "#D4AF37"  # Brand accents, highlights, important labels
SECONDARY_TEXT = "#A0A4A8"   # Helper text, captions, disabled items

# Success green (complements the palette)
SUCCESS_GREEN = "#4CAF50"

# Dark-mode backgrounds
DARK_BG_PRIMARY = "#0D0D0D"
DARK_BG_SECONDARY = "#1F252A"
DARK_BG_TERTIARY = "#3A4044"

# Light-mode backgrounds (defined for completeness; terminal TUI uses dark)
LIGHT_BG_PRIMARY = "#F7F8F9"
LIGHT_BG_SECONDARY = "#FFFFFF"
LIGHT_BG_TERTIARY = "#E6E9EC"

# ---------------------------------------------------------------------------
# Semantic color map  (used by menu.py / commands via ``menu.colors``)
#
# Keys are referenced throughout the TUI as  ``colors['primary']`` etc.
# ---------------------------------------------------------------------------
AEGIS_COLORS = {
    "primary": SECONDARY_BLUE,          # Headers, titles, spinner
    "secondary": PRIMARY_RED,           # CTAs, threats, high priority
    "accent": COMPLEMENTARY_GOLD,       # Brand accents, highlights
    "dark": DARK_BG_PRIMARY,            # Darkest background
    "dark_sec": DARK_BG_SECONDARY,      # Secondary dark background
    "dark_tert": DARK_BG_TERTIARY,      # Tertiary dark background
    "success": SUCCESS_GREEN,           # Positive status, confirmations
    "error": PRIMARY_RED,               # Errors, failures, delete actions
    "warning": COMPLEMENTARY_GOLD,      # Warnings, paused state
    "info": SECONDARY_BLUE,             # Informational, queued state
    "text": "#FFFFFF",                  # Primary text
    "dim": SECONDARY_TEXT,              # Secondary / helper text
}

# ---------------------------------------------------------------------------
# Rich Theme object -- can be passed to ``Console(theme=...)`` for
# console-wide semantic markup like ``[error]...[/error]``.
# ---------------------------------------------------------------------------
AEGIS_RICH_THEME = Theme({
    "error": f"bold {PRIMARY_RED}",
    "warning": f"{COMPLEMENTARY_GOLD}",
    "success": f"{SUCCESS_GREEN}",
    "info": f"{SECONDARY_BLUE}",
    "dim": f"{SECONDARY_TEXT}",
    "accent": f"{COMPLEMENTARY_GOLD}",
    "primary": f"{SECONDARY_BLUE}",
    "heading": f"bold {SECONDARY_BLUE}",
})
