from ..utils import parse_agent_identifier
from ..constants import DEFAULT_COLORS


def handle_set(menu, args):
    """Select an agent by index, client_id, or hostname."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    if not args:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    selection = args[0]
    selected_agent = parse_agent_identifier(selection, menu.displayed_agents, menu.agents)

    if selected_agent:
        menu.selected_agent = selected_agent
        hostname = selected_agent.hostname

        # In multi-account mode, assume into the agent's account so SDK
        # calls (asset search, domain lookup, etc.) target the right tenant.
        if getattr(menu, 'multi_account_mode', False):
            acct_info = menu.agent_account_map.get(selected_agent.client_id, {})
            acct_email = acct_info.get('account_email')
            if acct_email:
                try:
                    menu.sdk.accounts.assume_role(acct_email)
                except Exception as e:
                    menu.console.print(f"[{colors['warning']}]  Warning: failed to assume account {acct_email}: {e}[/{colors['warning']}]")

        menu.console.print(f"\n  Selected: {hostname}\n")
        # Pre-fetch home directory listing so cp tab-completion is instant
        if hasattr(menu, 'prefetch_agent_home'):
            menu.prefetch_agent_home(selected_agent)
    else:
        displayed_count = len(menu.displayed_agents)
        menu.console.print(f"\n[{colors['error']}]  Agent not found:[/{colors['error']}] {selection}")
        menu.console.print(f"[{colors['dim']}]  Use agent number (1-{displayed_count}), client ID, or hostname[/{colors['dim']}]\n")
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
