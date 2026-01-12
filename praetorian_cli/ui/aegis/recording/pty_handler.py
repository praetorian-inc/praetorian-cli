"""PTY wrapper for subprocess with I/O multiplexing."""
import os
import sys
import pty
import select
import termios
import tty
import subprocess
import signal
import struct
import fcntl
from typing import Callable, Optional, Tuple


class PTYHandler:
    """Handles PTY allocation and I/O multiplexing for SSH subprocess."""

    def __init__(self, command: list, env: dict = None):
        """
        Initialize PTY handler with command to execute.

        Args:
            command: Command list to execute (e.g., ["ssh", "user@host"])
            env: Optional environment dict (defaults to os.environ)
        """
        self.command = command
        self.env = env or os.environ.copy()
        self.master_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None

    def spawn(self) -> Tuple[int, subprocess.Popen]:
        """
        Spawn command with PTY allocation.

        Returns:
            Tuple of (master_fd, process)

        Raises:
            OSError: If PTY allocation fails
        """
        # Create master/slave PTY pair
        self.master_fd, slave_fd = pty.openpty()

        # Spawn subprocess with slave as stdin/stdout/stderr
        self.process = subprocess.Popen(
            self.command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=self.env,
            preexec_fn=os.setsid  # Create new session (become session leader)
        )

        # Parent doesn't need slave FD
        os.close(slave_fd)

        return self.master_fd, self.process

    def io_loop(self, recorder_callback: Optional[Callable[[bytes], None]] = None):
        """
        Main I/O multiplexing loop.

        Forwards data between:
        - User terminal (stdin) → Master PTY → SSH process
        - SSH process → Master PTY → User terminal (stdout) + Recorder

        Args:
            recorder_callback: Optional function to call with output data for recording
        """
        if not self.master_fd or not self.process:
            raise RuntimeError("Must call spawn() before io_loop()")

        # Save terminal attributes for restoration
        old_tty_attrs = None
        try:
            old_tty_attrs = termios.tcgetattr(sys.stdin)
            # Set terminal to raw mode (pass through control sequences)
            tty.setraw(sys.stdin.fileno())
        except (termios.error, AttributeError):
            # Not a TTY or unsupported terminal
            pass

        try:
            while self.process.poll() is None:
                # Wait for data from master PTY or stdin (100ms timeout)
                readable, _, _ = select.select(
                    [self.master_fd, sys.stdin.fileno()],
                    [],
                    [],
                    0.1
                )

                for fd in readable:
                    if fd == self.master_fd:
                        # SSH → User terminal + Recorder
                        try:
                            data = os.read(self.master_fd, 4096)
                            if data:
                                # Write to user's terminal
                                sys.stdout.buffer.write(data)
                                sys.stdout.buffer.flush()

                                # Call recorder callback
                                if recorder_callback:
                                    recorder_callback(data)
                        except OSError:
                            break  # PTY closed

                    elif fd == sys.stdin.fileno():
                        # User → SSH
                        try:
                            data = os.read(sys.stdin.fileno(), 4096)
                            if data:
                                os.write(self.master_fd, data)
                        except OSError:
                            break  # Stdin closed

        finally:
            # Restore terminal attributes
            if old_tty_attrs:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_attrs)
                except:
                    pass

    def setup_signal_handlers(self):
        """Set up signal handlers for window resize (SIGWINCH)."""
        def handle_sigwinch(signum, frame):
            """Forward terminal resize to subprocess."""
            if self.master_fd:
                try:
                    # Get current terminal size
                    term_size = os.get_terminal_size()
                    # Set PTY size using ioctl
                    winsize = struct.pack("HHHH", term_size.lines, term_size.columns, 0, 0)
                    fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
                except:
                    pass  # Ignore resize errors

        signal.signal(signal.SIGWINCH, handle_sigwinch)
