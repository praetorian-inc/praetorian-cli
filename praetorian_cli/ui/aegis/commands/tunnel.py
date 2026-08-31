from rich.prompt import Confirm

from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


ACTIONS = ("create", "remove")
ALIASES = {"delete": "remove", "rm": "remove"}


def handle_tunnel(menu, args):
    """Create or remove Cloudflare tunnel configuration for the selected Aegis agent."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        parsed = _parse_args(args)
    except ValueError as exc:
        menu.console.print(f"[{colors['error']}]Error: {exc}[/{colors['error']}]")
        show_tunnel_help(menu)
        return

    if parsed['help'] or not parsed['action']:
        show_tunnel_help(menu)
        return

    agent_id, legacy = _selected_agent_target(menu)
    if not agent_id:
        menu.console.print("\n  No Aegis agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    action = parsed['action']
    if not parsed['yes'] and not Confirm.ask(f"\n  {action.title()} Cloudflare tunnel on agent {agent_id}?"):
        menu.console.print('  Cancelled\n')
        menu.pause()
        return

    try:
        if action == 'create':
            response = menu.sdk.aegis.create_cloudflare_tunnel(agent_id, legacy=legacy)
            _print_create_result(menu, agent_id, response)
        else:
            response = menu.sdk.aegis.remove_cloudflare_tunnel(agent_id, legacy=legacy)
            _print_remove_result(menu, agent_id, response)
    except Exception as exc:
        menu.console.print(f"\n[{colors['error']}]Tunnel {action} error: {exc}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def show_tunnel_help(menu):
    help_text = """
  Aegis Tunnel Commands

  tunnel create [--yes]      Create and install a Cloudflare tunnel on the selected agent
  tunnel remove [--yes]      Remove Cloudflare tunnel configuration from the selected agent

  Aegis v1 uses its Velociraptor client ID; Aegis v2 uses its endpoint UUID.

  Examples:
    set 1
    tunnel create --yes
    tunnel remove
"""
    menu.console.print(help_text)
    menu.pause()


def complete(menu, text, tokens):
    if getattr(menu, 'selected_agent', None) is None:
        return []
    if len(tokens) <= 1:
        return [action for action in ACTIONS if action.startswith(text)]
    if len(tokens) == 2 and tokens[1] not in ACTIONS:
        return [action for action in ACTIONS if action.startswith(text)]
    if text.startswith('-'):
        return [option for option in ('--yes', '--help', '-y', '-h') if option.startswith(text)]
    return []


def _parse_args(args):
    parsed = {'action': None, 'yes': False, 'help': False}
    for token in args:
        value = token.lower()
        if value in ('--help', '-h', 'help'):
            parsed['help'] = True
            continue
        if value in ('--yes', '-y'):
            parsed['yes'] = True
            continue
        if parsed['action'] is not None:
            raise ValueError(f'unexpected argument: {token}')
        parsed['action'] = ALIASES.get(value, value)

    if parsed['action'] is not None and parsed['action'] not in ACTIONS:
        raise ValueError(f"unknown tunnel action: {parsed['action']}")
    return parsed


def _selected_agent_target(menu):
    agent = getattr(menu, 'selected_agent', None)
    if not agent:
        return '', False
    return agent_display_id(agent).strip(), not is_v2_agent(agent)


def _print_create_result(menu, endpoint_id, response):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    response = response if isinstance(response, dict) else {}
    tunnel_info = response.get('tunnelInfo') or {}

    menu.console.print(f"\n[{colors['success']}]✓ Cloudflare tunnel install queued[/{colors['success']}]")
    menu.console.print(f"  Agent: {endpoint_id}")
    if response.get('installTaskId'):
        menu.console.print(f"  Task ID: {response['installTaskId']}")
    if response.get('hostname'):
        menu.console.print(f"  Hostname: {response['hostname']}")
    if tunnel_info.get('tunnelName'):
        menu.console.print(f"  Tunnel: {tunnel_info['tunnelName']}")
    if response.get('message'):
        menu.console.print(f"  Message: {response['message']}")


def _print_remove_result(menu, endpoint_id, response):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    response = response if isinstance(response, dict) else {}

    menu.console.print(f"\n[{colors['success']}]✓ Cloudflare tunnel removal queued[/{colors['success']}]")
    menu.console.print(f"  Agent: {endpoint_id}")
    if response.get('taskId'):
        menu.console.print(f"  Task ID: {response['taskId']}")
    if response.get('message'):
        menu.console.print(f"  Message: {response['message']}")
