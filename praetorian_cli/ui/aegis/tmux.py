"""Tmux backend for managing SSH sessions in split panes."""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional


# Color rotation for pane borders
PANE_COLORS = ["cyan", "green", "yellow", "magenta", "red", "blue"]


@dataclass
class PaneInfo:
    """Tracks a tmux pane hosting an SSH session."""
    pane_id: str
    agent: object
    user: str
    public_hostname: str
    color: str
    created_at: float
    as_window: bool = False
    title: str = ""


class TmuxBackend:
    """Manage SSH sessions in tmux panes.

    Detection modes:
      1. Inside tmux ($TMUX set): split panes natively in the current window.
      2. Outside tmux (tmux installed): create an external session on a
         private socket ``aegis-<PID>``.
      3. No tmux: ``available`` is False; caller should fall back to blocking SSH.
    """

    def __init__(self):
        self._panes: List[PaneInfo] = []
        self._color_idx = 0
        self._tmux_path: Optional[str] = None
        self._native: bool = False
        self._socket: Optional[str] = None
        self._session_created: bool = False
        self._tui_pane_id: Optional[str] = None
        self._detect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._tmux_path is not None

    @property
    def native(self) -> bool:
        return self._native

    @property
    def socket(self) -> Optional[str]:
        return self._socket

    @property
    def panes(self) -> List[PaneInfo]:
        return list(self._panes)

    def create_pane(self, ssh_command: str, agent, user: str,
                    public_hostname: str, as_window: bool = False,
                    title: str = None) -> Optional[PaneInfo]:
        """Open a new tmux pane (or window) running *ssh_command*.

        The SSH command is run as the pane's process so that the pane
        automatically closes when the connection ends.

        *title* is shown in the pane border; defaults to *public_hostname*.

        Returns a ``PaneInfo`` on success, ``None`` on failure.
        """
        if not self.available:
            return None

        color = PANE_COLORS[self._color_idx % len(PANE_COLORS)]
        self._color_idx += 1
        pane_title = title or public_hostname

        try:
            if self._native:
                pane_id = self._create_native_pane(as_window, ssh_command)
            else:
                self._ensure_session()
                pane_id = self._create_external_pane(as_window, ssh_command)

            if not pane_id:
                return None

            self._style_pane(pane_id, pane_title, color)

            info = PaneInfo(
                pane_id=pane_id,
                agent=agent,
                user=user,
                public_hostname=public_hostname,
                color=color,
                created_at=time.monotonic(),
                as_window=as_window,
                title=pane_title,
            )
            self._panes.append(info)
            return info

        except Exception:
            return None

    def kill_pane(self, pane_id: str) -> None:
        """Kill a single pane and remove it from tracking."""
        try:
            self._tmux_cmd("kill-pane", "-t", pane_id)
        except Exception:
            pass
        self._panes = [p for p in self._panes if p.pane_id != pane_id]

    def kill_all(self) -> None:
        """Kill all tracked panes and, in external mode, the whole session."""
        for pane in list(self._panes):
            try:
                self._tmux_cmd("kill-pane", "-t", pane.pane_id)
            except Exception:
                pass
        self._panes.clear()

        if not self._native and self._session_created:
            try:
                self._tmux_cmd("kill-session", "-t", "aegis")
            except Exception:
                pass
            self._session_created = False

    def is_pane_alive(self, pane_id: str) -> bool:
        """Check whether a tmux pane still exists."""
        try:
            out = self._tmux_cmd("list-panes", "-a", "-F", "#{pane_id}")
            return pane_id in out.splitlines()
        except Exception:
            return False

    def prune_dead(self) -> None:
        """Remove entries for panes that no longer exist."""
        try:
            out = self._tmux_cmd("list-panes", "-a", "-F", "#{pane_id}")
            alive = set(out.splitlines())
        except Exception:
            return
        self._panes = [p for p in self._panes if p.pane_id in alive]

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _detect(self) -> None:
        self._tmux_path = shutil.which("tmux")
        if not self._tmux_path:
            return

        if os.environ.get("TMUX"):
            self._native = True
            # Capture the TUI's pane ID so we can refocus after splits
            try:
                self._tui_pane_id = self._tmux_cmd(
                    "display-message", "-p", "#{pane_id}",
                )
            except Exception:
                self._tui_pane_id = None
        else:
            self._socket = f"aegis-{os.getpid()}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _tmux_cmd(self, *args: str) -> str:
        """Run a tmux command and return stripped stdout."""
        cmd: List[str] = [self._tmux_path]
        if self._socket:
            cmd += ["-L", self._socket]
        cmd += list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def _ensure_session(self) -> None:
        """Lazily create a detached external session (first SSH only)."""
        if self._session_created:
            return
        self._tmux_cmd("new-session", "-d", "-s", "aegis", "-x", "200", "-y", "50")
        self._session_created = True

    def _refocus_tui(self) -> None:
        """Switch focus back to the TUI pane after a split."""
        if self._tui_pane_id:
            try:
                self._tmux_cmd("select-pane", "-t", self._tui_pane_id)
            except Exception:
                pass

    def _create_native_pane(self, as_window: bool, command: str) -> Optional[str]:
        """Split inside the current tmux window.

        *command* is run as the pane process; when it exits the pane closes.
        """
        if as_window:
            out = self._tmux_cmd(
                "new-window", "-P", "-F", "#{pane_id}", command,
            )
            return out

        existing = len(self._panes)
        if existing == 0:
            # First pane: horizontal split, SSH on the right at ~70%
            out = self._tmux_cmd(
                "split-window", "-h", "-l", "70%", "-P", "-F", "#{pane_id}",
                command,
            )
        else:
            # Alternate vertical / horizontal splits for subsequent panes
            flag = "-v" if existing % 2 == 1 else "-h"
            out = self._tmux_cmd(
                "split-window", flag, "-P", "-F", "#{pane_id}",
                command,
            )

        # Rebalance: main-vertical keeps TUI on the left at ~30%
        try:
            self._tmux_cmd("select-layout", "main-vertical")
            self._tmux_cmd(
                "set-window-option", "main-pane-width", "30%",
            )
        except Exception:
            pass

        return out

    def _create_external_pane(self, as_window: bool, command: str) -> Optional[str]:
        """Create a pane in the external session.

        *command* is run as the pane process; when it exits the pane closes.
        """
        if as_window:
            out = self._tmux_cmd(
                "new-window", "-t", "aegis", "-P", "-F", "#{pane_id}",
                command,
            )
            return out

        if not self._panes:
            # Reuse the initial pane that new-session created.
            # Use ``exec`` to replace the shell so the pane closes on exit.
            out = self._tmux_cmd(
                "list-panes", "-t", "aegis", "-F", "#{pane_id}",
            )
            pane_id = out.splitlines()[0] if out else None
            if pane_id:
                time.sleep(0.2)
                self._tmux_cmd(
                    "send-keys", "-t", pane_id, f"exec {command}", "Enter",
                )
            return pane_id

        # Split the last pane
        last = self._panes[-1].pane_id
        flag = "-v" if len(self._panes) % 2 == 1 else "-h"
        out = self._tmux_cmd(
            "split-window", flag, "-t", last, "-P", "-F", "#{pane_id}",
            command,
        )
        return out

    def _style_pane(self, pane_id: str, title: str, color: str) -> None:
        """Set pane title and colored border."""
        try:
            self._tmux_cmd(
                "select-pane", "-t", pane_id, "-T", title,
            )
        except Exception:
            pass
        try:
            self._tmux_cmd(
                "set-option", "-t", pane_id, "pane-border-style", f"fg={color}",
            )
        except Exception:
            pass
        try:
            self._tmux_cmd(
                "set-option", "-t", pane_id, "pane-active-border-style", f"fg={color}",
            )
        except Exception:
            pass
        # Show pane titles / borders
        try:
            self._tmux_cmd("set-option", "pane-border-status", "top")
        except Exception:
            pass
