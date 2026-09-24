from rich.prompt import Confirm

from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


ACTIONS = ("status", "create", "remove")
ALIASES = {"delete": "remove", "rm": "remove"}


def handle_tunnel(menu, args):
    """Inspect, create, or remove tunnel configuration for the selected Aegis agent."""
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
    if action == 'status':
        if legacy:
            menu.console.print(
                "\n  Tunnel status is available only for Aegis v2 endpoints.\n"
            )
            menu.pause()
            return
        try:
            response = menu.sdk.aegis.get_cloudflare_tunnel_status(agent_id)
            _print_status_result(menu, agent_id, response)
        except Exception as exc:
            menu.console.print(
                f"\n[{colors['error']}]Tunnel status error: {exc}[/{colors['error']}]"
            )
        menu.console.print()
        menu.pause()
        return

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

  tunnel status              Show configuration and runtime health for an Aegis v2 tunnel
  tunnel create [--yes]      Create and install a Cloudflare tunnel on the selected agent
  tunnel remove [--yes]      Remove Cloudflare tunnel configuration from the selected agent

  Status is available only for Aegis v2 endpoints. Create/remove also support
  legacy Aegis agents using their Velociraptor client ID.

  Examples:
    set 1
    tunnel status
    tunnel create --yes
    tunnel remove
"""
    menu.console.print(help_text)
    menu.pause()


def complete(menu, text, tokens):
    selected_agent = getattr(menu, 'selected_agent', None)
    if selected_agent is None:
        return []
    actions = ACTIONS if is_v2_agent(selected_agent) else ('create', 'remove')
    if len(tokens) <= 1:
        return [action for action in actions if action.startswith(text)]
    if len(tokens) == 2 and tokens[1] not in actions:
        return [action for action in actions if action.startswith(text)]
    if text.startswith('-'):
        options = (
            ('--help', '-h')
            if len(tokens) > 1 and tokens[1] == 'status'
            else ('--yes', '--help', '-y', '-h')
        )
        return [option for option in options if option.startswith(text)]
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
    if parsed['action'] == 'status' and parsed['yes']:
        raise ValueError('--yes is only valid with tunnel create or tunnel remove')
    return parsed


def _selected_agent_target(menu):
    agent = getattr(menu, 'selected_agent', None)
    if not agent:
        return '', False
    return agent_display_id(agent).strip(), not is_v2_agent(agent)


def _print_status_result(menu, endpoint_id, response):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    response = response if isinstance(response, dict) else {}
    configuration = response.get('configuration')
    configuration = configuration if isinstance(configuration, dict) else {}
    runtime = response.get('runtime')
    runtime = runtime if isinstance(runtime, dict) else {}

    menu.console.print(
        f"\n[{colors['primary']}]Cloudflare tunnel status[/{colors['primary']}]"
    )
    _print_value(menu, 'Endpoint', endpoint_id)
    _print_value(menu, 'Configuration', _format_status(configuration.get('state')))
    _print_optional_value(menu, 'Hostname', configuration.get('hostname'))
    _print_optional_value(menu, 'Tunnel', configuration.get('tunnelName'))
    _print_value(menu, 'Runtime', _format_status(runtime.get('state')))
    _print_value(menu, 'Readiness', _format_status(runtime.get('reason')))
    _print_optional_value(menu, 'Observed', runtime.get('observedAt'))
    _print_optional_value(menu, 'Detail', runtime.get('detail'))

    if 'authorizedUsers' in runtime:
        authorized_users = runtime.get('authorizedUsers')
        users = (
            ', '.join(str(user) for user in authorized_users) or 'None'
            if isinstance(authorized_users, list)
            else 'Unknown'
        )
        _print_value(menu, 'Authorized users', users)

    _print_component(menu, 'Service', runtime.get('service'), (
        ('load', 'loadState'),
        ('active', 'activeState'),
        ('sub', 'subState'),
        ('result', 'result'),
        ('exit code', 'exitCode'),
        ('exit status', 'exitStatus'),
    ))
    _print_component(menu, 'Connector', runtime.get('connector'), (
        ('state', 'state'),
        ('ready connections', 'readyConnections'),
        ('detail', 'detail'),
    ))
    _print_component(menu, 'Origin', runtime.get('origin'), (
        ('state', 'state'),
        ('detail', 'detail'),
    ))

    last_error = runtime.get('lastError')
    if isinstance(last_error, dict):
        observed_at = last_error.get('observedAt')
        message = last_error.get('message')
        detail = ' — '.join(
            str(value) for value in (observed_at, message) if value not in (None, '')
        )
        _print_optional_value(menu, 'Last error', detail)

    network_logs = runtime.get('networkLogs')
    if isinstance(network_logs, list) and network_logs:
        menu.console.print('  Network diagnostics:', markup=False)
        for entry in network_logs:
            if not isinstance(entry, dict):
                continue
            observed_at = entry.get('observedAt') or 'unknown time'
            kind = entry.get('kind') or 'unknown'
            message = entry.get('message') or ''
            menu.console.print(
                f'    {observed_at} [{kind}] {message}'.rstrip(),
                markup=False,
            )


def _print_component(menu, label, value, fields):
    if not isinstance(value, dict):
        return
    parts = [
        f'{display}={value[key]}'
        for display, key in fields
        if value.get(key) not in (None, '')
    ]
    if parts:
        _print_value(menu, label, ', '.join(parts))


def _print_optional_value(menu, label, value):
    if value not in (None, ''):
        _print_value(menu, label, value)


def _print_value(menu, label, value):
    menu.console.print(f'  {label}: {value or "Unknown"}', markup=False)


def _format_status(value):
    return str(value or 'unknown').replace('_', ' ').title()


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
