import logging
from ..utils import parse_agent_identifier
from ..constants import DEFAULT_COLORS

logger = logging.getLogger(__name__)


def handle_set(menu, args):
    """Select an agent by index, client_id, or hostname."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    multi_account_mode = getattr(menu, 'multi_account_mode', False)
    agent_account_map = getattr(menu, 'agent_account_map', {})

    if not args:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    selection = args[0]
    selected_agent = parse_agent_identifier(selection, menu.displayed_agents, menu.agents)

    if selected_agent:
        hostname = selected_agent.hostname

        # In multi-account mode, assume into the agent's account so SDK
        # calls (asset search, domain lookup, etc.) target the right tenant.
        # Must succeed before we commit to the selection.
        if multi_account_mode:
            # Prefer account info attached directly to agent (avoids client_id collisions)
            acct_info = getattr(selected_agent, '_account_info', None) or agent_account_map.get(selected_agent.client_id, {})
            acct_email = acct_info.get('account_email') if acct_info else None
            if not acct_email:
                logger.warning('No account email resolved for agent %s (client_id=%s)', hostname, selected_agent.client_id)
                menu.console.print(f"[{colors['error']}]  Could not resolve an account for {hostname}.[/{colors['error']}]")
                menu.pause()
                return
            try:
                menu.sdk.accounts.assume_role(acct_email)
            except Exception as e:
                logger.error('Failed to assume role for %s: %s', acct_email, e)
                menu.console.print(f"[{colors['error']}]  Failed to assume account {acct_email}: {e}[/{colors['error']}]")
                menu.pause()
                return

        menu.selected_agent = selected_agent
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
