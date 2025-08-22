from ..utils import parse_agent_identifier


def handle_set(menu, args):
    """Select an agent by index, client_id, or hostname."""
    if not args:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    selection = args[0]
    selected_agent = parse_agent_identifier(selection, menu.agents)

    if selected_agent:
        menu.selected_agent = selected_agent
        hostname = getattr(selected_agent, 'hostname', 'Unknown')
        menu.console.print(f"\n  Selected: {hostname}\n")
    else:
        menu.console.print(f"\n[red]  Agent not found:[/red] {selection}")
        menu.console.print(f"[dim]  Use agent number (1-{len(menu.agents)}), client ID, or hostname[/dim]\n")
        menu.pause()


def complete(menu, text, tokens):
    suggestions = []
    try:
        for idx, agent in enumerate(menu.agents or [], 1):
            hostname = getattr(agent, 'hostname', None)
            client_id = getattr(agent, 'client_id', None)
            suggestions.append(str(idx))
            if hostname:
                suggestions.append(str(hostname))
            if client_id:
                suggestions.append(str(client_id))
    except Exception:
        pass
    return [s for s in suggestions if s and s.startswith(text)]

