import re

from rich.prompt import Confirm

from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


ACTIONS = ("add", "remove")
ALIASES = {"del": "remove", "delete": "remove", "rm": "remove"}
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")


def handle_user(menu, args):
    """Add or remove Linux users through management on the selected Aegis agent."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        parsed = _parse_args(args)
    except ValueError as exc:
        menu.console.print(f"[{colors['error']}]Error: {exc}[/{colors['error']}]")
        show_user_help(menu)
        return

    if parsed['help'] or not parsed['action']:
        show_user_help(menu)
        return

    agent_id, legacy = _selected_agent_target(menu)
    if not agent_id:
        menu.console.print("\n  No Aegis agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    username = parsed['username']
    if not username or not USERNAME_RE.match(username):
        menu.console.print(f"[{colors['error']}]Error: invalid Linux username[/{colors['error']}]")
        menu.pause()
        return

    action = parsed['action']
    action_label = 'add' if action == 'add' else 'remove'
    if not parsed['yes']:
        remove_home_note = ' and remove home directory' if parsed['remove_home'] else ''
        if not Confirm.ask(f"\n  {action_label.title()} user '{username}' on agent {agent_id}{remove_home_note}?"):
            menu.console.print('  Cancelled\n')
            menu.pause()
            return

    try:
        if action == 'add':
            response = menu.sdk.aegis.add_system_user(agent_id, username, legacy=legacy)
            _print_result(menu, 'User add queued', agent_id, username, response)
        else:
            response = menu.sdk.aegis.remove_system_user(
                agent_id,
                username,
                remove_home=parsed['remove_home'],
                legacy=legacy,
            )
            _print_result(menu, 'User removal queued', agent_id, username, response)
    except Exception as exc:
        menu.console.print(f"\n[{colors['error']}]User {action_label} error: {exc}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def show_user_help(menu):
    help_text = """
  Aegis User Commands

  user add <username> [--yes]                    Add a Linux user on the selected agent
  user remove <username> [--remove-home] [--yes] Remove a Linux user from the selected agent

  Aegis v1 uses its Velociraptor client ID; Aegis v2 uses its endpoint UUID.

  Examples:
    set 1
    user add pentester --yes
    user remove pentester --remove-home
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
        return [option for option in ('--remove-home', '--yes', '--help', '-y', '-h') if option.startswith(text)]
    return []


def _parse_args(args):
    parsed = {'action': None, 'username': None, 'remove_home': False, 'yes': False, 'help': False}
    for token in args:
        value = token.lower()
        if value in ('--help', '-h', 'help'):
            parsed['help'] = True
            continue
        if value in ('--yes', '-y'):
            parsed['yes'] = True
            continue
        if value == '--remove-home':
            parsed['remove_home'] = True
            continue
        if parsed['action'] is None:
            parsed['action'] = ALIASES.get(value, value)
            continue
        if parsed['username'] is None:
            parsed['username'] = token
            continue
        raise ValueError(f'unexpected argument: {token}')

    if parsed['action'] is not None and parsed['action'] not in ACTIONS:
        raise ValueError(f"unknown user action: {parsed['action']}")
    if parsed['remove_home'] and parsed['action'] != 'remove':
        raise ValueError('--remove-home is only valid with user remove')
    return parsed


def _selected_agent_target(menu):
    agent = getattr(menu, 'selected_agent', None)
    if not agent:
        return '', False
    return agent_display_id(agent).strip(), not is_v2_agent(agent)


def _print_result(menu, label, endpoint_id, username, response):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    response = response if isinstance(response, dict) else {}

    menu.console.print(f"\n[{colors['success']}]✓ {label}[/{colors['success']}]")
    menu.console.print(f"  Agent: {endpoint_id}")
    menu.console.print(f"  Username: {username}")
    if response.get('taskId'):
        menu.console.print(f"  Task ID: {response['taskId']}")
    if response.get('status'):
        menu.console.print(f"  Status: {response['status']}")
    if response.get('message'):
        menu.console.print(f"  Message: {response['message']}")
