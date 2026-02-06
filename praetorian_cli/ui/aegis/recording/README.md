# Aegis Session Recording

Comprehensive session recording for aegis SSH connections using PTY wrapper and Asciicast v2 format.

## Features

- **Always-on recording** with opt-out via environment variable
- **Complete terminal capture** including colors, control sequences, and resize events
- **Async writing** to avoid impacting SSH performance
- **Graceful degradation** when recording fails (SSH continues)
- **Standard format** (Asciicast v2) for playback with asciinema tools

## Usage

### Automatic Recording

SSH sessions are automatically recorded by default:

```bash
praetorian aegis ssh agent-name
# Session will be recorded to ~/.praetorian/recordings/YYYY-MM-DD/agent_timestamp_id.cast
```

### Opt-Out of Recording

Set the `PRAETORIAN_NO_RECORD` environment variable:

```bash
PRAETORIAN_NO_RECORD=1 praetorian aegis ssh agent-name
```

Or add to your shell profile for permanent opt-out:

```bash
export PRAETORIAN_NO_RECORD=1
```

### Playback Recordings

Install asciinema:

```bash
pip install asciinema
```

Play a recording:

```bash
asciinema play ~/.praetorian/recordings/2026-01-12/agent-xyz_20260112-143022_a1b2c3.cast
```

Upload for sharing:

```bash
asciinema upload recording.cast
```

## Recording Location

Recordings are stored in:

```
~/.praetorian/recordings/YYYY-MM-DD/agent-name_YYYYMMdd-HHMMSS_session-id.cast
```

Example:
```
~/.praetorian/recordings/2026-01-12/prod-web-01_20260112-143022_a1b2c3.cast
```

## Architecture

### Components

1. **SessionRecorder** (`session_recorder.py`)
   - Orchestrates PTY handler and recording writer
   - Generates timestamped recording paths
   - Handles opt-out and graceful fallback

2. **PTYHandler** (`pty_handler.py`)
   - Allocates PTY master/slave pair
   - Multiplexes I/O between SSH, user terminal, and recorder
   - Handles terminal resize signals (SIGWINCH)

3. **AsciinemaWriter** (`asciinema_writer.py`)
   - Writes Asciicast v2 format with async buffering
   - Queue-based non-blocking writes
   - UTF-8 encoding with error replacement

### Data Flow

```
SSH Command → SessionRecorder.run()
            → PTYHandler.spawn(ssh_cmd)
            → pty.openpty() creates master/slave pair
            → subprocess.Popen(ssh_cmd, stdin=slave, stdout=slave, stderr=slave)
            → I/O loop: master → AsciinemaWriter.write_event() → ~/.praetorian/recordings/
            → subprocess.wait() → SessionRecorder reports path
```

## Error Handling

The recording system uses graceful degradation:

- **Recording initialization fails**: Warning shown, SSH continues without recording
- **PTY allocation fails**: Warning shown, falls back to `subprocess.run()`
- **Write errors**: Silently ignored, SSH continues
- **Directory creation fails**: Warning shown, SSH continues

**SSH functionality is never blocked by recording failures.**

## Format Details

Recordings use [Asciicast v2 format](https://github.com/asciinema/asciinema/blob/develop/doc/asciicast-v2.md):

- Line 1: JSON header with terminal dimensions and metadata
- Lines 2+: Newline-delimited JSON events `[timestamp, event_type, data]`

### Custom Metadata Fields

The header includes custom fields for aegis sessions:

- `agent_name`: Name of the aegis agent
- `agent_id`: Client ID of the agent
- `user`: SSH username
- `session_id`: Unique session identifier

Example header:
```json
{"version": 2, "width": 80, "height": 24, "timestamp": 1736697627, "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}, "title": "SSH to prod-web-01", "agent_name": "prod-web-01", "agent_id": "C.abc123", "user": "admin", "session_id": "a1b2c3"}
```

## Testing

Run tests:

```bash
# Unit tests
pytest tests/test_recording/test_asciinema_writer.py -v
pytest tests/test_recording/test_pty_handler.py -v
pytest tests/test_recording/test_session_recorder.py -v

# Integration tests
pytest tests/test_recording/test_integration.py -v -m integration

# All recording tests
pytest tests/test_recording/ -v
```

## Performance

- **Latency overhead**: < 5ms per keystroke (async writes)
- **Memory usage**: Bounded queue size (events written in background)
- **Disk usage**: ~10-50 KB per minute for typical sessions

## Troubleshooting

### Recording not created

Check:
1. Is `PRAETORIAN_NO_RECORD` environment variable set?
2. Does `~/.praetorian/recordings/` directory have write permissions?
3. Check stderr for warning messages

### Playback shows garbled output

Ensure terminal encoding is UTF-8:
```bash
export LANG=en_US.UTF-8
```

### Recording file is empty

Check:
1. Did the SSH session run successfully?
2. Was the session very short (< 1 second)?
3. Check file permissions on recording directory

## Future Enhancements

- Compression support (gzip .cast files)
- Retention policies (auto-delete after N days)
- Search/index recordings (SQLite metadata database)
- Web-based playback interface
