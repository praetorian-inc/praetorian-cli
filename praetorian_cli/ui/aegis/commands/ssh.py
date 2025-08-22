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

    # Extract '-u/--user' from args while passing the rest through to ssh
    user = None
    options = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '-u' or a == '--user':
            if i + 1 < len(args):
                user = args[i + 1]
                i += 2
                continue
        elif a.startswith('--user='):
            user = a.split('=', 1)[1]
            i += 1
            continue
        elif a.startswith('-u') and a != '-u':
            # support '-uadmin' form
            user = a[2:]
            i += 1
            continue
        options.append(a)
        i += 1

    # If user provided via -u/--user, strip any '-l <name>' occurrences to avoid conflicts
    if user:
        filtered = []
        skip_next = False
        for j, tok in enumerate(options):
            if skip_next:
                skip_next = False
                continue
            if tok == '-l' and j + 1 < len(options):
                skip_next = True
                continue
            filtered.append(tok)
        options = filtered

    try:
        menu.sdk.aegis.ssh_to_agent(
            agent=menu.selected_agent,
            options=options,
            user=user,
            display_info=True
        )
    except Exception as e:
        menu.console.print(f"[red]SSH error: {e}[/red]")
        menu.pause()


def complete(menu, text, tokens):
    opts = ['help', '-h', '--help', '-u', '--user', '-l', '-i', '-L', '-R', '-D', '-o', '-F', '-p', '-v', '-vv', '-vvv', '-4', '-6', '-A', '-a', '-C', '-N', '-T', '-q']
    return [o for o in opts if o.startswith(text)]
