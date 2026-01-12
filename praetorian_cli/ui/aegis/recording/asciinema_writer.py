"""Asciicast v2 format writer with async buffering."""
import json
import time
import threading
import os
from queue import Queue
from pathlib import Path
from typing import Optional


class AsciinemaWriter:
    """Writes terminal session recordings in Asciicast v2 format."""

    def __init__(self, filepath: Path, width: int, height: int, metadata: dict):
        """
        Initialize writer with recording path and terminal dimensions.

        Args:
            filepath: Path to write .cast file
            width: Terminal width in columns
            height: Terminal height in rows
            metadata: Custom metadata dict (agent_name, agent_id, user, title, etc.)
        """
        self.filepath = filepath
        self.file: Optional[object] = None
        self.start_time = time.time()
        self.write_queue: Queue = Queue()
        self.writer_thread: Optional[threading.Thread] = None
        self.metadata = metadata

        # Build Asciicast v2 header
        self.header = {
            "version": 2,
            "width": width,
            "height": height,
            "timestamp": int(self.start_time),
            "env": {
                "SHELL": metadata.get("shell", os.environ.get("SHELL", "")),
                "TERM": metadata.get("term", os.environ.get("TERM", "xterm-256color"))
            },
            "title": metadata.get("title", ""),
            # Custom metadata extensions (Asciicast v2 allows arbitrary fields)
            "agent_name": metadata.get("agent_name"),
            "agent_id": metadata.get("agent_id"),
            "user": metadata.get("user"),
            "session_id": metadata.get("session_id")
        }

    def start(self) -> bool:
        """
        Start recording session by opening file and starting writer thread.

        Returns:
            True if recording started successfully, False on error (graceful degradation)
        """
        try:
            # Create parent directories if needed
            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            # Open file with line buffering
            self.file = open(self.filepath, 'w', buffering=1)

            # Write header line
            self.file.write(json.dumps(self.header) + '\n')
            self.file.flush()

            # Start background writer thread
            self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
            self.writer_thread.start()

            return True

        except (IOError, OSError, PermissionError) as e:
            # Graceful degradation - recording fails but SSH continues
            return False

    def write_event(self, data: bytes, event_type: str = "o"):
        """
        Queue event for async writing (non-blocking).

        Args:
            data: Raw bytes from terminal
            event_type: "o" for output (stdout/stderr), "i" for input (stdin)
        """
        if not self.writer_thread:
            return  # Recording not started, skip silently

        timestamp = time.time() - self.start_time
        # Decode with replacement to handle invalid UTF-8
        text = data.decode('utf-8', errors='replace')
        event = [timestamp, event_type, text]
        self.write_queue.put(event)

    def _writer_loop(self):
        """Background thread that writes events from queue to file."""
        while True:
            event = self.write_queue.get()
            if event is None:  # Sentinel value for shutdown
                break

            try:
                self.file.write(json.dumps(event) + '\n')
            except (IOError, OSError):
                # Swallow write errors to avoid crashing SSH session
                pass

    def close(self):
        """Flush queue and close recording file."""
        if self.writer_thread:
            # Send shutdown sentinel
            self.write_queue.put(None)
            # Wait for thread to finish (with timeout)
            self.writer_thread.join(timeout=2.0)

        if self.file:
            try:
                self.file.close()
            except:
                pass  # Ignore close errors
