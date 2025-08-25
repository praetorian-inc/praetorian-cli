def handle_list(menu, args):
    """List agents with optional offline flag."""
    show_offline = '--all' in args or '-a' in args

    if not menu.agents:
        menu.load_agents()

    menu.show_agents_list(show_offline=show_offline)
    menu.pause()


def complete(menu, text, tokens):
    return [o for o in ['--all', '-a'] if o.startswith(text)]

