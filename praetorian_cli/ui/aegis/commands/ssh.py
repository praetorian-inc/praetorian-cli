from praetorian_cli.handlers.ssh_utils import SSHArgumentParser

def _print_help(menu):
    help_text = """
  SSH Command

  Pass native ssh flags directly; we tunnel the host.
  Username: use '-u/--user <user>' or native '-l <user>'.

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
    ssh -L 8080:localhost:80 -D 1080 -i ~/.ssh/id_ed25519
    ssh -l admin -o StrictHostKeyChecking=no
"""
    menu.console.print(f"\n{help_text}")


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

    # Also support '-h/--help'
    if any(a in ('-h', '--help') for a in args):
        _print_help(menu)
        menu.pause()
        return
    
    parser = SSHArgumentParser(console=menu.console)
    
    # Validate agent first
    if not parser.validate_agent_ssh_availability(menu.selected_agent):
        menu.pause()
        return
    
    # Parse arguments using shared parser
    parsed_options = parser.parse_ssh_args(args)
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
    
    try:
        menu.sdk.aegis.ssh_to_agent(
            agent=menu.selected_agent,
            options=options,
            user=parsed_options.get('user'),
            display_info=True
        )
    except Exception as e:
        menu.console.print(f"[red]SSH error: {e}[/red]")
        menu.pause()


def complete(menu, text, tokens):
    opts = ['help', '-h', '--help', '-u', '--user', '-l', '-i', '-L', '-R', '-D', '-o', '-F', '-p', '-v', '-vv', '-vvv', '-4', '-6', '-A', '-a', '-C', '-N', '-T', '-q']
    return [o for o in opts if o.startswith(text)]
