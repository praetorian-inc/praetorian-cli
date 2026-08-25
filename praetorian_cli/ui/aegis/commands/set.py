import logging
from ..utils import (
    agent_account_info,
    agent_display_id,
    is_v2_agent,
    matching_agent_hostnames,
    parse_agent_identifier,
)
from ..constants import DEFAULT_COLORS

logger = logging.getLogger(__name__)


def handle_set(menu, args):
    """Select an agent by index, client_id, endpoint ID, or hostname."""
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
            # Prefer account info attached directly to agent (avoids identifier collisions)
            display_id = agent_display_id(selected_agent)
            acct_info = agent_account_info(selected_agent, agent_account_map)
            acct_email = acct_info.get('account_email') if acct_info else None
            if not acct_email:
                logger.warning(
                    'No account email resolved for agent %s (id=%s)',
                    hostname,
                    display_id,
                )
                menu.console.print(
                    f"[{colors['error']}]  Could not resolve an account for {hostname}.[/{colors['error']}]"
                )
                menu.pause()
                return
            try:
                menu.sdk.accounts.assume_role(acct_email)
            except Exception as e:
                logger.error('Failed to assume role for %s: %s', acct_email, e)
                menu.console.print(
                    f"[{colors['error']}]  Failed to assume account {acct_email}: {e}[/{colors['error']}]"
                )
                menu.pause()
                return
            setattr(selected_agent, '_account_info', acct_info)

        menu.selected_agent = selected_agent
        selected_label = f"\n  Selected: {hostname}"
        if is_v2_agent(selected_agent):
            display_id = agent_display_id(selected_agent)
            selected_label += f" [v2] ({display_id})"
            acct_info = agent_account_info(selected_agent, agent_account_map)
            account_name = None
            if acct_info:
                account_name = acct_info.get('display_name') or acct_info.get('account_email')
            if account_name:
                selected_label += f" — {account_name}"
        menu.console.print(f"{selected_label}\n")
        # Pre-fetch home directory listing so cp tab-completion is instant
        if hasattr(menu, 'prefetch_agent_home'):
            menu.prefetch_agent_home(selected_agent)
    else:
        displayed_count = len(menu.displayed_agents)
        if len(matching_agent_hostnames(selection, menu.agents)) > 1:
            menu.console.print(
                f"\n[{colors['error']}]  Multiple agents match hostname:[/{colors['error']}] {selection}"
            )
            menu.console.print(
                f"[{colors['dim']}]  Use agent number (1-{displayed_count}), "
                f"client ID, or endpoint ID[/{colors['dim']}]\n"
            )
        else:
            menu.console.print(
                f"\n[{colors['error']}]  Agent not found:[/{colors['error']}] {selection}"
            )
            menu.console.print(
                f"[{colors['dim']}]  Use agent number (1-{displayed_count}), "
                f"client ID, endpoint ID, or hostname[/{colors['dim']}]\n"
            )
        menu.pause()


def complete(menu, text, tokens):
    suggestions = []
    for idx, agent in enumerate(menu.agents, 1):
        suggestions.append(str(idx))
        if agent.hostname:
            suggestions.append(agent.hostname)
        display_id = agent_display_id(agent)
        if display_id:
            suggestions.append(display_id)
    return [s for s in suggestions if s.startswith(text)]
