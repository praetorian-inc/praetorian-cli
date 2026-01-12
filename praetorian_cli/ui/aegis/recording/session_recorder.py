"""Session recorder orchestrator."""
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import our recording components
from .pty_handler import PTYHandler
from .asciinema_writer import AsciinemaWriter


class SessionRecorder:
    """Orchestrates PTY handler and recording writer for SSH sessions."""

    def __init__(self, command: list, metadata: dict):
        """
        Initialize session recorder.

        Args:
            command: SSH command list to execute
            metadata: Session metadata (agent_name, agent_id, user, etc.)
        """
        self.command = command
        self.metadata = metadata
        self.recording_path = self._generate_recording_path()

    def _generate_recording_path(self) -> Path:
        """
        Generate timestamped recording path.

        Returns:
            Path like: ~/.praetorian/recordings/YYYY-MM-DD/agent_YYYYMMdd-HHMMSS_session.cast
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = uuid.uuid4().hex[:6]
        agent_name = self.metadata.get("agent_name", "unknown")
        date_dir = datetime.now().strftime("%Y-%m-%d")

        base_dir = Path.home() / ".praetorian" / "recordings" / date_dir
        filename = f"{agent_name}_{timestamp}_{session_id}.cast"
        return base_dir / filename

    def run(self) -> int:
        """
        Execute SSH command with recording (or without if opted out).

        Returns:
            SSH process exit code
        """
        # Check opt-out environment variable
        if os.environ.get("PRAETORIAN_NO_RECORD"):
            # Fall back to regular subprocess without recording
            result = subprocess.run(self.command)
            return result.returncode

        # Get terminal size
        try:
            term_size = os.get_terminal_size()
            width = term_size.columns
            height = term_size.lines
        except OSError:
            # Not a TTY, use defaults
            width, height = 80, 24

        # Create writer
        writer = AsciinemaWriter(
            filepath=self.recording_path,
            width=width,
            height=height,
            metadata=self.metadata
        )

        # Try to start recording
        if not writer.start():
            # Recording failed - fall back to regular subprocess
            import sys
            print(f"\033[33m⚠️  Failed to start recording, continuing without it\033[0m", file=sys.stderr)
            result = subprocess.run(self.command)
            return result.returncode

        # Create PTY handler
        pty_handler = PTYHandler(self.command)

        try:
            # Spawn SSH process with PTY
            master_fd, process = pty_handler.spawn()

            # Set up signal handlers for window resize
            pty_handler.setup_signal_handlers()

            # Run I/O loop with recording callback
            pty_handler.io_loop(writer.write_event)

            # Wait for process to complete
            exit_code = process.wait()

            # Show success message
            import sys
            print(f"\n\033[32m📹 Session recorded to: {self.recording_path}\033[0m", file=sys.stderr)

            return exit_code

        except OSError as e:
            # PTY allocation failed - fall back to regular subprocess
            import sys
            print(f"\033[33m⚠️  PTY allocation failed, recording disabled: {e}\033[0m", file=sys.stderr)
            result = subprocess.run(self.command)
            return result.returncode

        finally:
            # Always close writer
            writer.close()

            # Clean up PTY master FD
            if pty_handler.master_fd:
                try:
                    os.close(pty_handler.master_fd)
                except:
                    pass
