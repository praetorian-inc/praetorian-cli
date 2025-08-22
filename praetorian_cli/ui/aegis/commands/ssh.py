import argparse


def _build_parser():
    parser = argparse.ArgumentParser(prog='ssh', add_help=False)
    parser.add_argument('-u', '--user', help='Remote user name')
    parser.add_argument('-L', '--local-forward', action='append', default=[], metavar='[bind_address:]port:host:hostport', help='Local port forward (repeatable)')
    parser.add_argument('-R', '--remote-forward', action='append', default=[], metavar='[bind_address:]port:host:hostport', help='Remote port forward (repeatable)')
    parser.add_argument('-D', '--dynamic-forward', metavar='[bind_address:]port', help='Dynamic SOCKS proxy port')
    parser.add_argument('-i', '--key', metavar='IDENTITY_FILE', help='Identity (private key) file')
    parser.add_argument('--ssh-opts', metavar='OPTS', help='Extra ssh options string')
    parser.add_argument('-h', '--help', action='store_true', help='Show ssh options')
    return parser


def _print_help(menu):
    parser = _build_parser()
    usage = parser.format_help()
    menu.console.print(f"\n{usage}")


def handle_ssh(menu, args):
    """SSH into the selected agent with optional port forwarding."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    # Accept `ssh help` too
    if len(args) and args[0].lower() == 'help':
        _print_help(menu)
        menu.pause()
        return

    parser = _build_parser()
    try:
        ns, _ = parser.parse_known_args(args)
    except SystemExit:
        menu.console.print("[red]Invalid ssh arguments[/red]")
        menu.pause()
        return

    if getattr(ns, 'help', False):
        _print_help(menu)
        menu.pause()
        return

    try:
        menu.sdk.aegis.ssh_to_agent(
            agent=menu.selected_agent,
            user=ns.user,
            local_forward=ns.local_forward,
            remote_forward=ns.remote_forward,
            dynamic_forward=ns.dynamic_forward,
            key=ns.key,
            ssh_opts=ns.ssh_opts,
            display_info=True
        )
    except Exception as e:
        menu.console.print(f"[red]SSH error: {e}[/red]")
        menu.pause()


def complete(menu, text, tokens):
    opts = [
        '-u', '--user',
        '-L', '--local-forward',
        '-R', '--remote-forward',
        '-D', '--dynamic-forward',
        '-i', '--key',
        '--ssh-opts',
        '-h', '--help', 'help'
    ]
    return [o for o in opts if o.startswith(text)]

