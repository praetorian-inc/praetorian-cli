from ..utils import parse_agent_identifier


def handle_set(menu, args):
    """Select an agent by index, client_id, or hostname."""
    if not args:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    selection = args[0]
    
    # Try numeric selection from display first, then fall back to name/ID matching
    if selection.isdigit():
        display_idx = int(selection)
        display_map = getattr(menu, 'display_agent_map', {})
        selected_agent = display_map.get(display_idx) if display_map else parse_agent_identifier(selection, menu.agents)
    else:
        selected_agent = parse_agent_identifier(selection, menu.agents)

    if selected_agent:
        menu.selected_agent = selected_agent
        menu.console.print(f"\n  Selected: {selected_agent.hostname}\n")
    else:
        display_count = len(getattr(menu, 'display_agent_map', menu.agents))
        menu.console.print(f"\n[red]  Agent not found:[/red] {selection}")
        menu.console.print(f"[dim]  Use agent number (1-{display_count}), client ID, or hostname[/dim]\n")
        menu.pause()


def complete(menu, text, tokens):
    suggestions = []
    display_map = getattr(menu, 'display_agent_map', {})
    
    if display_map:
        for display_idx, agent in display_map.items():
            suggestions.append(str(display_idx))
            if agent.hostname:
                suggestions.append(agent.hostname)
            if agent.client_id:
                suggestions.append(agent.client_id)
    else:
        # Fallback for tests/edge cases
        for idx, agent in enumerate(menu.agents, 1):
            suggestions.append(str(idx))
            if agent.hostname:
                suggestions.append(agent.hostname)
            if agent.client_id:
                suggestions.append(agent.client_id)
    
    return [s for s in suggestions if s.startswith(text)]
