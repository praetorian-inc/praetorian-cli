from ..utils import parse_agent_identifier


def handle_set(menu, args):
    """Select an agent by index, client_id, or hostname."""
    if not args:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    selection = args[0]
    selected_agent = parse_agent_identifier(selection, menu.displayed_agents, menu.agents)

    if selected_agent:
        menu.selected_agent = selected_agent
        hostname = selected_agent.hostname
        menu.console.print(f"\n  Selected: {hostname}\n")
    else:
        displayed_count = len(menu.displayed_agents)
        menu.console.print(f"\n[red]  Agent not found:[/red] {selection}")
        menu.console.print(f"[dim]  Use agent number (1-{displayed_count}), client ID, or hostname[/dim]\n")
        menu.pause()


def complete(menu, text, tokens):
    suggestions = []
    for idx, agent in enumerate(menu.agents, 1):
        suggestions.append(str(idx))
        if agent.hostname:
            suggestions.append(agent.hostname)
        if agent.client_id:
            suggestions.append(agent.client_id)
    return [s for s in suggestions if s.startswith(text)]
