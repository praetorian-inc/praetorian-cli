from rich.box import MINIMAL
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from praetorian_cli.ui.conversation.endpoint_status import (
    format_endpoint_execution_status,
)
from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


SUBCOMMANDS = ('launch', 'list', 'status', 'pause', 'resume', 'stop', 'delete', 'help')
HUNT_STATUSES = ('active', 'paused', 'completed', 'stopped', 'expired', 'errored')


def handle_hunt(menu, args):
    """Manage endpoint-bound AI Hunts from the Aegis console."""
    if not args or args[0].lower() in ('help', '-h', '--help'):
        show_hunt_help(menu)
        return

    subcommand = args[0].lower()
    if subcommand not in SUBCOMMANDS:
        _print_message(
            menu,
            f'Unknown hunt subcommand: {subcommand}',
            'error',
        )
        show_hunt_help(menu)
        return
    if len(args) > 1 and args[1].lower() in ('help', '-h', '--help'):
        show_hunt_help(menu)
        return

    endpoint = _selected_hunt_endpoint(menu)
    if endpoint is None:
        return

    handlers = {
        'launch': launch_hunt,
        'list': list_hunts,
        'status': show_hunt_status,
        'pause': pause_hunt,
        'resume': resume_hunt,
        'stop': stop_hunt,
        'delete': delete_hunt,
    }
    handlers[subcommand](menu, endpoint, args[1:])


def complete(_menu, text, tokens):
    if len(tokens) <= 1:
        return [command for command in SUBCOMMANDS if command.startswith(text)]
    if len(tokens) == 2 and tokens[1] not in SUBCOMMANDS:
        return [command for command in SUBCOMMANDS if command.startswith(text)]

    subcommand = tokens[1]
    if not text.startswith('-'):
        return []
    if subcommand == 'launch':
        options = (
            '--prompt', '--scope', '--expires', '--scope-level',
            '--aggressiveness', '--yes', '--help',
        )
    elif subcommand == 'list':
        options = ('--status', '--all', '--help')
    elif subcommand in ('stop', 'delete'):
        options = ('--yes', '--help')
    else:
        options = ('--help',)
    return [option for option in options if option.startswith(text)]


def show_hunt_help(menu):
    menu.console.print("""
  Aegis v2 AI Hunt Commands

  hunt launch --scope <asset-key> --prompt <objective> [options]
  hunt list [--status <status>] [--all]
  hunt status <hunt-id>
  hunt pause|resume|stop|delete <hunt-id>

  The selected Aegis v2 endpoint is used automatically. Hunt scope must
  contain existing internal asset keys. If the endpoint is unavailable,
  the Hunt waits without falling back to external compute.
""")
    menu.pause()


def launch_hunt(menu, endpoint, args):
    try:
        options = _parse_launch_args(args)
        if options['help']:
            show_hunt_help(menu)
            return
        objective = options['prompt'] or Prompt.ask('  Hunt objective').strip()
        scopes = options['scopes'] or [Prompt.ask('  Internal scope asset key').strip()]
        if not objective:
            raise ValueError('hunt objective is required')
        if any(not scope for scope in scopes):
            raise ValueError('at least one internal scope asset key is required')
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return

    endpoint_id = agent_display_id(endpoint)
    endpoint_name = endpoint.hostname or endpoint_id
    endpoint_state = 'online' if endpoint.is_online else 'offline'
    confirmation = Text(
        f'Run this AI Hunt through {_safe(endpoint_name)} '
        f'({_safe(endpoint_id)}, {endpoint_state})? If unavailable, the Hunt '
        'waits without external compute fallback'
    )
    if not options['yes'] and not Confirm.ask(confirmation, default=False):
        menu.console.print('  Cancelled')
        menu.pause()
        return

    try:
        result = menu.sdk.hunts.create(
            prompt=objective,
            expires_hours=options['expires'],
            agent='hannibal',
            scope=scopes,
            scope_level=options['scope_level'],
            aggressiveness=options['aggressiveness'],
            endpoint_required=True,
            endpoint_id=endpoint_id,
            endpoint_confirmed=True,
        )
    except Exception as exc:
        _print_message(menu, f'AI Hunt launch failed: {exc}', 'error')
    else:
        _print_message(menu, 'AI Hunt launched', 'success')
        menu.console.print(f'  Hunt: {_hunt_id(result) or "unknown"}')
        menu.console.print(f'  Endpoint: {endpoint_id}')
    menu.pause()


def list_hunts(menu, endpoint, args):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    try:
        options = _parse_list_args(args)
        if options['help']:
            show_hunt_help(menu)
            return
        hunts, _ = menu.sdk.hunts.list(
            status=options['status'],
            pages=10000 if options['all'] else 1,
        )
    except Exception as exc:
        _print_message(menu, f'Error listing AI Hunts: {exc}', 'error')
        menu.pause()
        return

    endpoint_id = agent_display_id(endpoint)
    hunts = [hunt for hunt in hunts if _belongs_to_endpoint(hunt, endpoint_id)]
    if not hunts:
        menu.console.print(f'  No AI Hunts found for endpoint {endpoint_id}.')
        menu.pause()
        return

    table = Table(
        title=Text(f'AI Hunts for {_safe(endpoint.hostname or endpoint_id)}'),
        box=MINIMAL,
        border_style=colors['dim'],
        header_style=f"bold {colors['primary']}",
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column('HUNT ID', style=f"bold {colors['success']}")
    table.add_column('STATUS')
    table.add_column('ITERATIONS', justify='right')
    table.add_column('FINDINGS', justify='right')
    table.add_column('OBJECTIVE')
    for hunt in hunts:
        table.add_row(
            Text(_hunt_id(hunt) or 'unknown'),
            Text(_safe(_value(hunt, 'status'))),
            Text(str(_value(hunt, 'iterationCount', 'iteration_count') or 0)),
            Text(str(_value(hunt, 'findingsCount', 'findings_count') or 0)),
            Text(_safe(_value(hunt, 'prompt'), limit=80)),
        )
    menu.console.print(table)
    menu.pause()


def show_hunt_status(menu, endpoint, args):
    hunt = _get_selected_hunt(menu, endpoint, args)
    if hunt is None:
        return

    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    table = Table(
        title=Text(f'AI Hunt {_hunt_id(hunt)}'),
        box=MINIMAL,
        border_style=colors['dim'],
        show_header=False,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column('Field', style=f"bold {colors['primary']}")
    table.add_column('Value')
    fields = (
        ('Status', _value(hunt, 'status')),
        ('Endpoint', _hunt_endpoint_id(hunt)),
        ('Iterations', _value(hunt, 'iterationCount', 'iteration_count') or 0),
        ('Findings', _value(hunt, 'findingsCount', 'findings_count') or 0),
        ('Created', _value(hunt, 'created')),
        ('Expires', _value(hunt, 'expiresAt', 'expires_at')),
        ('Objective', _value(hunt, 'prompt')),
        ('Last error', _value(hunt, 'lastError', 'last_error')),
    )
    for label, value in fields:
        table.add_row(Text(label), Text(_safe(value)))
    menu.console.print(table)

    try:
        status = menu.sdk.hunts.endpoint_execution_status(hunt)
    except Exception as exc:
        _print_message(
            menu,
            f'Endpoint execution status unavailable: {exc}',
            'warning',
        )
    else:
        rendered = format_endpoint_execution_status(status)
        if rendered:
            menu.console.print(Text(rendered))
    menu.pause()


def pause_hunt(menu, endpoint, args):
    _mutate_hunt(menu, endpoint, args, 'pause', 'paused')


def resume_hunt(menu, endpoint, args):
    _mutate_hunt(menu, endpoint, args, 'resume', 'resumed')


def stop_hunt(menu, endpoint, args):
    _mutate_hunt(menu, endpoint, args, 'stop', 'stopped', confirm=True)


def delete_hunt(menu, endpoint, args):
    _mutate_hunt(menu, endpoint, args, 'delete', 'deleted', confirm=True)


def _selected_hunt_endpoint(menu):
    selected = getattr(menu, 'selected_agent', None)
    if selected is None:
        menu.console.print("  No endpoint selected. Use 'set <id>' first.")
        menu.pause()
        return None
    if not is_v2_agent(selected) or str(getattr(selected, 'kind', '')).lower() != 'aegis':
        _print_message(
            menu,
            'AI Hunts require a selected Aegis v2 endpoint.',
            'error',
        )
        menu.pause()
        return None

    selected_id = agent_display_id(selected).lower()
    try:
        endpoints = menu.sdk.aegis.list_hunt_endpoints()
    except Exception as exc:
        _print_message(
            menu,
            f'Unable to validate the selected endpoint: {exc}',
            'error',
        )
        menu.pause()
        return None

    for endpoint in endpoints:
        if (
            is_v2_agent(endpoint)
            and str(getattr(endpoint, 'kind', '')).lower() == 'aegis'
            and agent_display_id(endpoint).lower() == selected_id
        ):
            return endpoint

    _print_message(
        menu,
        'The selected endpoint is no longer authorized for AI Hunts.',
        'error',
    )
    menu.pause()
    return None


def _get_selected_hunt(menu, endpoint, args):
    try:
        hunt_id, _yes = _parse_hunt_id_args(args)
        hunt = menu.sdk.hunts.get(hunt_id)
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return None
    except Exception as exc:
        _print_message(menu, f'Unable to load AI Hunt: {exc}', 'error')
        menu.pause()
        return None

    if not hunt:
        _print_message(menu, f'AI Hunt {hunt_id} was not found.', 'error')
        menu.pause()
        return None
    if not _belongs_to_endpoint(hunt, agent_display_id(endpoint)):
        _print_message(
            menu,
            f'AI Hunt {hunt_id} does not belong to the selected endpoint.',
            'error',
        )
        menu.pause()
        return None
    return hunt


def _mutate_hunt(menu, endpoint, args, method, past_tense, confirm=False):
    try:
        hunt_id, yes = _parse_hunt_id_args(args)
        hunt = menu.sdk.hunts.get(hunt_id)
        if not hunt:
            raise ValueError(f'AI Hunt {hunt_id} was not found')
        if not _belongs_to_endpoint(hunt, agent_display_id(endpoint)):
            raise ValueError(
                f'AI Hunt {hunt_id} does not belong to the selected endpoint'
            )
    except Exception as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return

    if confirm and not yes and not Confirm.ask(
        Text(f'{method.title()} AI Hunt {_safe(hunt_id)}?'),
        default=False,
    ):
        menu.console.print('  Cancelled')
        menu.pause()
        return

    try:
        getattr(menu.sdk.hunts, method)(hunt_id)
    except Exception as exc:
        _print_message(menu, f'Unable to {method} AI Hunt: {exc}', 'error')
    else:
        _print_message(
            menu,
            f'AI Hunt {hunt_id} {past_tense}.',
            'success',
        )
    menu.pause()


def _print_message(menu, message, color):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    menu.console.print(Text(_safe(message, limit=1000), style=colors[color]))


def _parse_launch_args(args):
    options = {
        'prompt': None,
        'scopes': [],
        'expires': 72,
        'scope_level': 'normal',
        'aggressiveness': 'balanced',
        'yes': False,
        'help': False,
    }
    value_options = {
        '-p': 'prompt', '--prompt': 'prompt',
        '-s': 'scope', '--scope': 'scope',
        '-e': 'expires', '--expires': 'expires',
        '--scope-level': 'scope_level',
        '--aggressiveness': 'aggressiveness',
    }
    index = 0
    while index < len(args):
        token = args[index]
        if token in ('-h', '--help', 'help'):
            options['help'] = True
            index += 1
            continue
        if token in ('-y', '--yes'):
            options['yes'] = True
            index += 1
            continue
        destination = value_options.get(token)
        if destination is None:
            raise ValueError(f'unknown option: {token}')
        if index + 1 >= len(args):
            raise ValueError(f'{token} requires a value')
        value = args[index + 1].strip()
        if destination == 'scope':
            options['scopes'].append(value)
        elif destination == 'expires':
            try:
                options['expires'] = int(value)
            except ValueError as exc:
                raise ValueError('--expires must be an integer') from exc
        else:
            options[destination] = value
        index += 2

    if not 1 <= options['expires'] <= 72:
        raise ValueError('--expires must be between 1 and 72')
    if options['scope_level'] not in ('normal', 'strict'):
        raise ValueError('--scope-level must be normal or strict')
    if options['aggressiveness'] not in ('cautious', 'balanced', 'aggressive'):
        raise ValueError(
            '--aggressiveness must be cautious, balanced, or aggressive'
        )
    return options


def _parse_list_args(args):
    options = {'status': None, 'all': False, 'help': False}
    index = 0
    while index < len(args):
        token = args[index]
        if token in ('-h', '--help', 'help'):
            options['help'] = True
            index += 1
        elif token == '--all':
            options['all'] = True
            index += 1
        elif token == '--status':
            if index + 1 >= len(args):
                raise ValueError('--status requires a value')
            options['status'] = args[index + 1].lower()
            index += 2
        else:
            raise ValueError(f'unknown option: {token}')
    if options['status'] and options['status'] not in HUNT_STATUSES:
        raise ValueError(f"--status must be one of {', '.join(HUNT_STATUSES)}")
    return options


def _parse_hunt_id_args(args):
    positional = []
    yes = False
    for token in args:
        if token in ('-h', '--help', 'help'):
            raise ValueError('a Hunt ID is required')
        if token in ('-y', '--yes'):
            yes = True
        elif token.startswith('-'):
            raise ValueError(f'unknown option: {token}')
        else:
            positional.append(token)
    if len(positional) != 1:
        raise ValueError('exactly one Hunt ID is required')
    return positional[0], yes


def _belongs_to_endpoint(hunt, endpoint_id):
    return bool(
        isinstance(hunt, dict)
        and _value(
            hunt,
            'endpointRequired',
            'endpoint_required',
            'EndpointRequired',
        )
        and _hunt_endpoint_id(hunt).lower() == _safe(endpoint_id).lower()
    )


def _hunt_endpoint_id(hunt):
    return _safe(_value(hunt, 'endpointId', 'endpoint_id', 'EndpointID'))


def _hunt_id(hunt):
    identifier = _value(hunt, 'uuid', 'id')
    if not identifier:
        identifier = _value(hunt, 'key')
    return _safe(identifier).removeprefix('#hunt#')


def _value(values, *keys):
    if not isinstance(values, dict):
        return None
    for key in keys:
        value = values.get(key)
        if value is not None:
            return value
    return None


def _safe(value, limit=500):
    if value is None:
        return ''
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in str(value)
    )
    return ' '.join(printable.split())[:limit]
