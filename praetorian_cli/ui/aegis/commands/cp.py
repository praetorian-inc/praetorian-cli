from praetorian_cli.handlers.ssh_utils import SSHArgumentParser
from ..constants import DEFAULT_COLORS


def _print_help(menu):
    help_text = """
  CP Command — Copy files to/from an agent via rsync (scp fallback)

  Use ':' prefix for remote paths.

  Usage:
    cp <local_path> :<remote_path>       Upload file/directory
    cp :<remote_path> <local_path>       Download file/directory

  Options:
    -u, --user USER       SSH username
    -i IDENTITY_FILE      Identity (private key) file
    --no-rsync            Force scp instead of rsync

  Examples:
    cp ./exploit.sh :/tmp/exploit.sh
    cp :/etc/passwd ./loot/passwd
    cp -u root ./tools :/opt/tools
    cp --no-rsync ./file.txt :/tmp/file.txt
"""
    menu.console.print(f"\n{help_text}")


def handle_cp(menu, args):
    """Copy files to/from the selected agent."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    if (len(args) and args[0].lower() == 'help') or any(a in ('-h', '--help') for a in args):
        _print_help(menu)
        menu.pause()
        return

    parser = SSHArgumentParser(console=menu.console)

    if not parser.validate_agent_ssh_availability(menu.selected_agent):
        menu.pause()
        return

    # Parse options and collect positional paths
    user = None
    key = None
    use_rsync = True
    paths = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-u', '--user'):
            if i + 1 >= len(args):
                menu.console.print("[red]Error: -u requires a username[/red]")
                menu.pause()
                return
            user = args[i + 1]
            i += 2
        elif arg in ('-i',):
            if i + 1 >= len(args):
                menu.console.print("[red]Error: -i requires a key file path[/red]")
                menu.pause()
                return
            key = args[i + 1]
            i += 2
        elif arg == '--no-rsync':
            use_rsync = False
            i += 1
        elif arg.startswith('-'):
            menu.console.print(f"[red]Error: Unknown option '{arg}'[/red]")
            menu.pause()
            return
        else:
            paths.append(arg)
            i += 1

    if len(paths) != 2:
        menu.console.print("[red]Error: cp requires exactly two paths (source and destination)[/red]")
        menu.console.print("[dim]Usage: cp <src> <dst>   (prefix remote path with ':')[/dim]")
        menu.pause()
        return

    src, dst = paths
    src_remote = src.startswith(':')
    dst_remote = dst.startswith(':')

    if src_remote and dst_remote:
        menu.console.print("[red]Error: both paths cannot be remote[/red]")
        menu.pause()
        return
    if not src_remote and not dst_remote:
        menu.console.print("[red]Error: one path must be remote (prefix with ':')[/red]")
        menu.pause()
        return

    if src_remote:
        direction = 'download'
        remote_path = src[1:]
        local_path = dst
    else:
        direction = 'upload'
        local_path = src
        remote_path = dst[1:]

    ssh_options = []
    if key:
        ssh_options.extend(['-i', key])

    try:
        menu.sdk.aegis.copy_to_agent(
            agent=menu.selected_agent,
            local_path=local_path,
            remote_path=remote_path,
            direction=direction,
            user=user,
            ssh_options=ssh_options,
            display_info=True,
            use_rsync=use_rsync,
        )
    except Exception as e:
        colors = getattr(menu, 'colors', DEFAULT_COLORS)
        menu.console.print(f"[{colors['error']}]Copy error: {e}[/{colors['error']}]")
        menu.pause()


def complete(_menu, text, _tokens):
    opts = ['help', '-h', '--help', '-u', '--user', '-i', '--no-rsync']
    return [o for o in opts if o.startswith(text)]
