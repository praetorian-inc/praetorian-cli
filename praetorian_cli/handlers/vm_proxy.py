"""
Engineer VM connection plumbing for `praetorian vm ssh` / `vm code-server`.

`run_ws_proxy` is the ssh ProxyCommand: it opens ONE WebSocket to the gateway's
/connect endpoint and dumb-pipes stdin<->ws<->stdout. ssh writes the SSH wire
protocol to our stdin (forwarded as binary frames); the gateway authenticates
the Cognito JWT, re-checks ownership, and splices the stream to sshd:22 inside
the VM; replies flow back ws->stdout. No AWS creds ever touch the laptop.

The URL builders are kept pure (no I/O) so they are unit-testable.
"""

import os
import select
import ssl
import sys
import threading
from urllib.parse import urlencode


def _to_ws_scheme(gateway: str) -> str:
    """ Normalize a gateway base to a ws/wss scheme (default wss when bare). """
    g = (gateway or '').strip()
    if g.startswith(('wss://', 'ws://')):
        return g
    if g.startswith('https://'):
        return 'wss://' + g[len('https://'):]
    if g.startswith('http://'):
        return 'ws://' + g[len('http://'):]
    return 'wss://' + g


def _to_https_scheme(gateway: str) -> str:
    """ Normalize a gateway base to an http/https scheme (default https when bare). """
    g = (gateway or '').strip()
    if g.startswith(('https://', 'http://')):
        return g
    if g.startswith('wss://'):
        return 'https://' + g[len('wss://'):]
    if g.startswith('ws://'):
        return 'http://' + g[len('ws://'):]
    return 'https://' + g


def build_connect_url(gateway: str, token: str, vm_id: str, target: str, account: str = '') -> str:
    """ Build the gateway /connect WebSocket URL the ProxyCommand dials. """
    base = _to_ws_scheme(gateway).rstrip('/')
    query = {'token': token, 'vm_id': vm_id, 'target': target}
    if account:
        query['account'] = account
    return f'{base}/connect?{urlencode(query)}'


def build_code_server_url(gateway: str, token: str) -> str:
    """ Build the browser code-server URL (the gateway plants the cookie from
        ?token= on first contact). """
    base = _to_https_scheme(gateway).rstrip('/')
    return f'{base}/code-server/?{urlencode({"token": token})}'


def run_ws_proxy(gateway: str, token: str, vm_id: str, target: str, account: str = '') -> int:
    """ Bridge stdin<->WebSocket<->stdout. Returns a process exit code. """
    try:
        import websocket  # websocket-client
    except ImportError:
        sys.stderr.write(
            "praetorian vm ssh needs the 'websocket-client' package "
            "(pip install websocket-client).\n")
        return 1

    url = build_connect_url(gateway, token, vm_id, target, account)
    # DEV STOPGAP (remove with real TLS / WI4-proper): a dev
    # gateway may present a self-signed cert; GUARD_VM_INSECURE_TLS=1 skips OUTER-TLS verification
    # (SSH wire is already E2E-encrypted). Unset keeps full verification.
    kwargs = {'enable_multithread': True}
    if os.environ.get('GUARD_VM_INSECURE_TLS', '').strip().lower() in ('1', 'true', 'yes'):
        kwargs['sslopt'] = {'cert_reqs': ssl.CERT_NONE}
    try:
        ws = websocket.create_connection(url, **kwargs)
    except Exception as e:  # noqa: BLE001 - surface any connect failure to ssh
        sys.stderr.write(f'engineer-vm proxy: connect failed: {e}\n')
        return 1

    in_fd = sys.stdin.fileno()
    out_fd = sys.stdout.fileno()
    done = threading.Event()

    def pump_inbound():
        # ws -> stdout
        try:
            while not done.is_set():
                data = ws.recv()
                if data is None or data == '' or data == b'':
                    break
                if isinstance(data, str):
                    data = data.encode()
                os.write(out_fd, data)
        except Exception:  # noqa: BLE001 - any read error ends the splice
            pass
        finally:
            done.set()

    reader = threading.Thread(target=pump_inbound, daemon=True)
    reader.start()

    # stdin -> ws (main thread). select keeps us responsive to a ws-side close
    # instead of blocking forever on a read after the inbound pump has ended.
    try:
        while not done.is_set():
            ready, _, _ = select.select([in_fd], [], [], 0.5)
            if not ready:
                continue
            chunk = os.read(in_fd, 65536)
            if not chunk:
                break
            ws.send_binary(chunk)
    except Exception:  # noqa: BLE001
        pass
    finally:
        done.set()
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass
    reader.join(timeout=1)
    return 0
