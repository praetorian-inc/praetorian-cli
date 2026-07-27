import time

from rich.table import Table
from rich.box import MINIMAL

from praetorian_cli.handlers.ssh_utils import SSHArgumentParser
from ..constants import DEFAULT_COLORS

def _print_help(menu):
    help_text = """
  SSH Command

  Pass native ssh flags directly; we tunnel the host.
  Username: use '-u/--user <user>' or native '-l <user>'.

  Subcommands:
    ssh                                    Open SSH (tmux pane when available)
    ssh list                               Show active SSH panes
    ssh kill <id|all>                      Kill an SSH pane by number or all

  tmux integration (auto-detected):
    --window                               Open SSH in a new tmux window instead of a split pane
    --block                                Force blocking SSH (no tmux, takes over terminal)

  Common options (forwarded to ssh):
    -L [bind_address:]port:host:hostport   Local port forward (repeatable)
    -R [bind_address:]port:host:hostport   Remote port forward (repeatable)
    -D [bind_address:]port                 Dynamic SOCKS proxy
    -i IDENTITY_FILE                       Identity (private key) file
    -l USER                                Remote username (alternative to -u/--user)
    -o OPTION=VALUE                        Extra ssh config option
    -p PORT                                SSH port
    -v/-vv/-vvv                            Verbose output

  Examples:
    ssh                                    SSH to selected agent in tmux pane
    ssh --window                           Open in new tmux window
    ssh --block                            Blocking SSH (old behavior)
    ssh -L 8080:localhost:80               SSH with port forward in tmux pane
    ssh list                               Show active SSH sessions
    ssh kill 1                             Kill first SSH pane
    ssh kill all                           Kill all SSH panes
"""
    menu.console.print(f"\n{help_text}")


def handle_ssh(menu, args):
    """SSH into the selected agent with optional port forwarding."""
    # Route subcommands before requiring a selected agent
    if len(args) and args[0].lower() == 'list':
        _handle_ssh_list(menu)
        return

    if len(args) and args[0].lower() == 'kill':
        _handle_ssh_kill(menu, args[1:])
        return

    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    # Accept `ssh help` too
    if len(args) and args[0].lower() == 'help':
        _print_help(menu)
        menu.pause()
        return

    # Also support '-h/--help'
    if any(a in ('-h', '--help') for a in args):
        _print_help(menu)
        menu.pause()
        return

    # Extract --window and --block flags before passing to SSHArgumentParser
    as_window = False
    force_block = False
    filtered_args = []
    for a in args:
        if a == '--window':
            as_window = True
        elif a == '--block':
            force_block = True
        else:
            filtered_args.append(a)

    parser = SSHArgumentParser(console=menu.console)

    # Validate agent first
    if not parser.validate_agent_ssh_availability(menu.selected_agent):
        menu.pause()
        return

    # Parse arguments using shared parser
    parsed_options = parser.parse_ssh_args(filtered_args)
    if not parsed_options:
        # Error already displayed by parser
        menu.pause()
        return

    # Build options list from parsed options for SDK
    options = parsed_options.get('passthrough', [])

    # Add structured options back as SSH flags
    for forward in parsed_options.get('local_forward', []):
        options.extend(['-L', forward])
    for forward in parsed_options.get('remote_forward', []):
        options.extend(['-R', forward])
    if parsed_options.get('dynamic_forward'):
        options.extend(['-D', parsed_options['dynamic_forward']])
    if parsed_options.get('key'):
        options.extend(['-i', parsed_options['key']])

    # Resolve user once (needed for both tmux and blocking paths)
    user = parsed_options.get('user')

    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    agent = menu.selected_agent

    # Try tmux path first (unless --block)
    if not force_block:
        tmux = getattr(menu, '_tmux', None)
        if tmux and tmux.available:
            if _ssh_via_tmux(menu, agent, options, user, as_window, colors):
                return

    # Fallback: blocking SSH
    _ssh_blocking(menu, agent, options, user, colors)


# ------------------------------------------------------------------
# Subcommands: list / kill
# ------------------------------------------------------------------

def _handle_ssh_list(menu):
    """Show a table of active SSH panes."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    tmux = getattr(menu, '_tmux', None)

    if not tmux or not tmux.available:
        menu.console.print(f"\n  [{colors['dim']}]tmux not available[/{colors['dim']}]\n")
        return

    # Prune dead panes before listing
    tmux.prune_dead()
    panes = tmux.panes

    if not panes:
        menu.console.print(f"\n  [{colors['dim']}]No active SSH panes[/{colors['dim']}]\n")
        return

    table = Table(
        show_header=True,
        header_style=f"bold {colors['primary']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False,
    )

    table.add_column("#", style=f"bold {colors['dim']}", width=4, no_wrap=True)
    table.add_column("HOST", style="white", min_width=15, no_wrap=True)
    table.add_column("USER", style=f"{colors['dim']}", width=12, no_wrap=True)
    table.add_column("UPTIME", style=f"{colors['dim']}", width=10, no_wrap=True)
    table.add_column("STATUS", width=12, no_wrap=True)

    now = time.monotonic()
    for i, pane in enumerate(panes, 1):
        hostname = pane.title or pane.public_hostname
        uptime = _format_uptime(now - pane.created_at)
        alive = tmux.is_pane_alive(pane.pane_id)
        status = (
            f"[{colors['success']}]connected[/{colors['success']}]"
            if alive
            else f"[{colors['error']}]closed[/{colors['error']}]"
        )
        table.add_row(str(i), hostname, pane.user, uptime, status)

    menu.console.print()
    menu.console.print(table)
    menu.console.print()


def _handle_ssh_kill(menu, args):
    """Kill an SSH pane by index or 'all'."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    tmux = getattr(menu, '_tmux', None)

    if not tmux or not tmux.available:
        menu.console.print(f"[{colors['error']}]tmux not available[/{colors['error']}]")
        menu.pause()
        return

    if not args:
        menu.console.print(f"[{colors['error']}]Usage: ssh kill <number|all>[/{colors['error']}]")
        menu.pause()
        return

    if args[0].lower() == 'all':
        count = len(tmux.panes)
        if not count:
            menu.console.print(f"[{colors['dim']}]No active SSH panes to kill[/{colors['dim']}]")
            return
        tmux.kill_all()
        menu.console.print(f"[{colors['success']}]Killed {count} SSH pane(s)[/{colors['success']}]")
        return

    try:
        idx = int(args[0])
    except ValueError:
        menu.console.print(f"[{colors['error']}]Invalid pane number: {args[0]}[/{colors['error']}]")
        menu.pause()
        return

    tmux.prune_dead()
    panes = tmux.panes
    if idx < 1 or idx > len(panes):
        menu.console.print(f"[{colors['error']}]No pane #{idx} (have {len(panes)} active)[/{colors['error']}]")
        menu.pause()
        return

    target = panes[idx - 1]
    hostname = target.title or target.public_hostname
    tmux.kill_pane(target.pane_id)
    menu.console.print(f"[{colors['success']}]Killed SSH pane #{idx} ({hostname})[/{colors['success']}]")


# ------------------------------------------------------------------
# SSH via tmux / blocking
# ------------------------------------------------------------------

def _ssh_via_tmux(menu, agent, options, user, as_window, colors):
    """Open SSH in a tmux pane. Returns True on success."""
    tmux = menu._tmux

    try:
        cmd_str = menu.sdk.aegis.build_ssh_command(
            agent=agent, options=options, user=user,
        )
    except Exception as e:
        menu.console.print(f"[{colors['error']}]SSH error: {e}[/{colors['error']}]")
        menu.pause()
        return True  # error handled, don't fall through to blocking

    hostname = agent.hostname or 'Unknown'
    public_hostname = agent.health_check.cloudflared_status.hostname
    ssh_user = user
    if not ssh_user:
        try:
            _, ssh_user = menu.sdk.aegis.api.get_current_user()
        except Exception:
            ssh_user = 'unknown'

    # Wrap command: on SSH failure, keep pane open so the error is visible
    wrapped_cmd = (
        f"{cmd_str} || {{ printf '\\n\\033[31mSSH connection failed. "
        f"Press Enter to close.\\033[0m\\n'; read _; }}"
    )

    pane = tmux.create_pane(
        ssh_command=wrapped_cmd,
        agent=agent,
        user=ssh_user,
        public_hostname=public_hostname,
        as_window=as_window,
        title=hostname,
    )

    if not pane:
        # Pane creation failed — caller should fall back to blocking
        menu.console.print(f"[{colors['warning']}]tmux pane creation failed, falling back to blocking SSH[/{colors['warning']}]")
        return False

    mode = "window" if as_window else "pane"
    menu.console.print(f"[{colors['success']}]SSH {mode} -> {hostname}[/{colors['success']}]")

    if not tmux.native and tmux.socket:
        menu.console.print(f"  [{colors['accent']}]Attach: tmux -L {tmux.socket} attach[/{colors['accent']}]")

    return True


def _ssh_blocking(menu, agent, options, user, colors):
    """Fall back to the original blocking subprocess.run() SSH."""
    try:
        menu.sdk.aegis.ssh_to_agent(
            agent=agent,
            options=options,
            user=user,
            display_info=True,
        )
    except Exception as e:
        menu.console.print(f"[{colors['error']}]SSH error: {e}[/{colors['error']}]")
        menu.pause()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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
    opts = [
        'list', 'kill', 'help', '-h', '--help',
        '--window', '--block',
        '-u', '--user', '-l', '-i', '-L', '-R', '-D', '-o', '-F', '-p',
        '-v', '-vv', '-vvv', '-4', '-6', '-A', '-a', '-C', '-N', '-T', '-q',
    ]
    return [o for o in opts if o.startswith(text)]
