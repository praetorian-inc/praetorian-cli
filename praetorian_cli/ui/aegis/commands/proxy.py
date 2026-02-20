"""Proxy command — start, list, and stop background SOCKS proxies."""

import subprocess
import time
from dataclasses import dataclass, field
from threading import Thread, Event

from ..constants import DEFAULT_COLORS


@dataclass
class ProxyInfo:
    port: int
    agent: object
    user: str
    public_hostname: str
    process: subprocess.Popen
    started_at: float
    monitor_thread: Thread
    stop_event: Event
    reconnect_count: int = 0
    max_reconnects: int = 5
    _ssh_cmd: list = field(default_factory=list)


def handle_proxy(menu, args):
    """Entry point — routes to start/list/stop/help."""
    if not args:
        _print_help(menu)
        menu.pause()
        return

    subcmd = args[0].lower()

    if subcmd in ('help', '-h', '--help'):
        _print_help(menu)
        menu.pause()
    elif subcmd == 'list':
        _handle_list(menu)
    elif subcmd == 'stop':
        _handle_stop(menu, args[1:])
    else:
        _handle_start(menu, args)


def _handle_start(menu, args):
    """Parse port + optional -u, validate agent, launch proxy."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    agent = menu.selected_agent
    if not getattr(agent, 'has_tunnel', False):
        menu.console.print(f"[{colors['error']}]Agent has no active tunnel[/{colors['error']}]")
        menu.pause()
        return

    # Parse args: first positional is port, -u <user> optional
    port = None
    user = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-u', '--user'):
            if i + 1 >= len(args):
                menu.console.print(f"[{colors['error']}]Error: -u requires a username[/{colors['error']}]")
                menu.pause()
                return
            user = args[i + 1]
            i += 2
        elif port is None:
            try:
                port = int(arg)
            except ValueError:
                menu.console.print(f"[{colors['error']}]Invalid port: {arg}[/{colors['error']}]")
                menu.pause()
                return
            i += 1
        else:
            i += 1

    if port is None:
        menu.console.print(f"[{colors['error']}]Usage: proxy <port> [-u user][/{colors['error']}]")
        menu.pause()
        return

    if port < 1 or port > 65535:
        menu.console.print(f"[{colors['error']}]Port must be between 1 and 65535[/{colors['error']}]")
        menu.pause()
        return

    proxies = getattr(menu, '_active_proxies', {})
    if port in proxies:
        menu.console.print(f"[{colors['warning']}]Proxy already running on port {port}[/{colors['warning']}]")
        menu.pause()
        return

    try:
        public_hostname = agent.health_check.cloudflared_status.hostname
    except Exception:
        menu.console.print(f"[{colors['error']}]Cannot determine agent hostname[/{colors['error']}]")
        menu.pause()
        return

    if not user:
        try:
            _, user = menu.sdk.aegis.api.get_current_user()
        except Exception as e:
            menu.console.print(f"[{colors['error']}]Failed to detect SSH user: {e}. Use -u to specify one.[/{colors['error']}]")
            menu.pause()
            return

    info = _start_proxy_process(port, agent, user, public_hostname)
    if info is None or info.process.poll() is not None:
        menu.console.print(f"[{colors['error']}]Failed to start proxy on port {port}[/{colors['error']}]")
        menu.pause()
        return

    if not hasattr(menu, '_active_proxies'):
        menu._active_proxies = {}
    menu._active_proxies[port] = info
    menu.console.print(f"[{colors['success']}]SOCKS proxy started on localhost:{port}[/{colors['success']}]")


def _start_proxy_process(port, agent, user, hostname):
    """Launch SSH SOCKS proxy and spawn monitor thread. Returns ProxyInfo."""
    ssh_cmd = [
        'ssh',
        '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-D', str(port),
        '-N',
        f'{user}@{hostname}',
    ]

    try:
        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None

    stop_event = Event()
    info = ProxyInfo(
        port=port,
        agent=agent,
        user=user,
        public_hostname=hostname,
        process=process,
        started_at=time.monotonic(),
        monitor_thread=None,
        stop_event=stop_event,
        _ssh_cmd=ssh_cmd,
    )

    thread = Thread(target=_monitor_proxy, args=(info,), daemon=True)
    info.monitor_thread = thread
    thread.start()

    return info


def _monitor_proxy(info):
    """Daemon thread — poll process, auto-reconnect on death with backoff."""
    _BASE_DELAY = 2.0
    _MAX_BACKOFF = 60.0

    while not info.stop_event.is_set():
        info.stop_event.wait(timeout=2.0)
        if info.stop_event.is_set():
            break
        if info.process.poll() is not None:
            # Process died
            if info.reconnect_count >= info.max_reconnects:
                break
            info.reconnect_count += 1
            delay = min(_BASE_DELAY * (2 ** (info.reconnect_count - 1)), _MAX_BACKOFF)
            if info.stop_event.wait(timeout=delay):
                break
            try:
                info.process = subprocess.Popen(
                    info._ssh_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Reset backoff on successful restart
                if info.process.poll() is None:
                    info.reconnect_count = 0
            except Exception:
                break


def _handle_list(menu):
    """Rich table of active proxies with status."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    proxies = getattr(menu, '_active_proxies', {})

    if not proxies:
        menu.console.print(f"\n  [{colors['dim']}]No active proxies[/{colors['dim']}]\n")
        return

    from rich.table import Table
    from rich.box import MINIMAL

    table = Table(
        show_header=True,
        header_style=f"bold {colors['primary']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False,
    )

    table.add_column("PORT", style=f"bold {colors['success']}", width=8, no_wrap=True)
    table.add_column("AGENT", style="white", min_width=15, no_wrap=True)
    table.add_column("USER", style=f"{colors['dim']}", width=12, no_wrap=True)
    table.add_column("UPTIME", style=f"{colors['dim']}", width=10, no_wrap=True)
    table.add_column("STATUS", width=12, no_wrap=True)

    now = time.monotonic()
    for port in sorted(proxies):
        info = proxies[port]
        hostname = getattr(info.agent, 'hostname', 'unknown')
        uptime = _format_uptime(now - info.started_at)
        alive = info.process.poll() is None
        status = f"[{colors['success']}]running[/{colors['success']}]" if alive else f"[{colors['error']}]dead[/{colors['error']}]"
        table.add_row(str(port), hostname, info.user, uptime, status)

    menu.console.print()
    menu.console.print(table)
    menu.console.print()


def _handle_stop(menu, args):
    """Stop by port or 'all'."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    proxies = getattr(menu, '_active_proxies', {})

    if not args:
        menu.console.print(f"[{colors['error']}]Usage: proxy stop <port|all>[/{colors['error']}]")
        menu.pause()
        return

    if args[0].lower() == 'all':
        if not proxies:
            menu.console.print(f"[{colors['dim']}]No active proxies to stop[/{colors['dim']}]")
            return
        stop_all_proxies(menu)
        menu.console.print(f"[{colors['success']}]All proxies stopped[/{colors['success']}]")
        return

    try:
        port = int(args[0])
    except ValueError:
        menu.console.print(f"[{colors['error']}]Invalid port: {args[0]}[/{colors['error']}]")
        menu.pause()
        return

    if port not in proxies:
        menu.console.print(f"[{colors['warning']}]No proxy running on port {port}[/{colors['warning']}]")
        menu.pause()
        return

    _stop_single_proxy(menu, port)
    menu.console.print(f"[{colors['success']}]Proxy on port {port} stopped[/{colors['success']}]")


def _stop_single_proxy(menu, port):
    """SIGTERM -> wait 3s -> SIGKILL, remove from dict."""
    proxies = getattr(menu, '_active_proxies', {})
    info = proxies.pop(port, None)
    if info is None:
        return
    info.stop_event.set()
    try:
        info.process.terminate()
        info.process.wait(timeout=3)
    except Exception:
        try:
            info.process.kill()
        except Exception:
            pass


def stop_all_proxies(menu):
    """Stop all proxies — called on TUI exit."""
    proxies = getattr(menu, '_active_proxies', {})
    ports = list(proxies.keys())
    for port in ports:
        _stop_single_proxy(menu, port)


def _format_uptime(seconds):
    """Format uptime: 45s / 3m / 1h20m."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes:
        return f"{hours}h{remaining_minutes}m"
    return f"{hours}h"


def complete(menu, text, tokens):
    """Tab complete subcommands + active ports."""
    subcommands = ['list', 'stop', 'help']
    # If first token after 'proxy' is 'stop', suggest ports + 'all'
    if len(tokens) >= 2 and tokens[1].lower() == 'stop':
        proxies = getattr(menu, '_active_proxies', {})
        options = ['all'] + [str(p) for p in sorted(proxies)]
        return [o for o in options if o.startswith(text)]
    return [s for s in subcommands if s.startswith(text)]


def _print_help(menu):
    """Show help text."""
    help_text = """
  Proxy Command — Background SOCKS proxy via SSH

  Usage:
    proxy <port> [-u user]       Start SOCKS proxy on localhost:<port>
    proxy list                   Show active proxies
    proxy stop <port>            Stop a specific proxy
    proxy stop all               Stop all proxies
    proxy help                   Show this help

  Examples:
    proxy 1080                   Start SOCKS proxy on port 1080
    proxy 9050 -u admin          Start proxy as specific user
    proxy list                   Show running proxies
    proxy stop 1080              Stop proxy on port 1080
    proxy stop all               Stop all proxies
"""
    menu.console.print(f"\n{help_text}")
