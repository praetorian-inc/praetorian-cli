import time

from rich.box import MINIMAL
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from praetorian_cli.ui.conversation.endpoint_status import (
    format_endpoint_execution_status,
)
from praetorian_cli.ui.entity_resolver import resolve_entity_reference
from praetorian_cli.ui.entity_selector import select_entity_keys
from praetorian_cli.ui.hunt_chat import (
    build_hunt_chat,
    select_hunt_conversation,
)
from praetorian_cli.ui.hunt_data import (
    build_hunt_findings,
    build_hunt_log,
    build_hunt_memory,
    build_hunt_memory_item,
    filter_hunt_findings,
)
from praetorian_cli.ui.hunt_defaults import (
    DEFAULT_FINISH_CRITERIA,
    DEFAULT_HUNT_DURATION_HOURS,
)
from praetorian_cli.ui.hunt_launch import configure_hunt_launch
from praetorian_cli.ui.hunt_workflows import browse_hunt_workflows
from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


SUBCOMMANDS = (
    'launch', 'list', 'status', 'findings', 'memory', 'log', 'chat',
    'pause', 'resume', 'stop', 'delete', 'help',
)
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
        'findings': show_hunt_findings,
        'memory': manage_hunt_memory,
        'log': show_hunt_log,
        'chat': chat_hunt,
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
            '--aggressiveness', '--finish-criteria', '--guardrails',
            '--custom-tag', '--model-tier', '--credential', '--yes', '--help',
        )
    elif subcommand == 'list':
        options = ('--status', '--all', '--help')
    elif subcommand in ('stop', 'delete'):
        options = ('--yes', '--help')
    elif subcommand == 'status':
        options = ('--workflows', '--help')
    elif subcommand == 'findings':
        options = ('--status', '--severity', '--details', '--evidence', '--all', '--help')
    elif subcommand == 'memory':
        options = ('--item', '--content', '--delete', '--yes', '--help')
    elif subcommand == 'log':
        options = ('--follow', '--interval', '--help')
    elif subcommand == 'chat':
        options = ('--conversation', '--message', '--help')
    else:
        options = ('--help',)
    return [option for option in options if option.startswith(text)]


def show_hunt_help(menu):
    menu.console.print("""
  Aegis v2 AI Hunt Commands

  hunt launch --prompt <objective> [--scope <hostname-or-IP>] [options]
  hunt list [--status <status>] [--all]
  hunt status <hunt-id> [--workflows]
  hunt findings <hunt-id> [--severity <level>] [--details]
  hunt memory <hunt-id> [--item <title>] [--content <text> | --delete]
  hunt log <hunt-id> [--follow]
  hunt chat <hunt-id> [--conversation <id>] [--message <guidance>]
  hunt pause|resume|stop|delete <hunt-id>

  The selected Aegis v2 endpoint is used automatically. When --scope is
  omitted, choose active internal targets from a searchable list. The launch
  wizard then reviews mandate, aggressiveness, credentials, guardrails,
  finish criteria, duration, finding tag, and model tier. Use --yes to accept
  flag/default values. --credential may be repeated, once per credential type.
  If the endpoint is unavailable, the Hunt waits without external fallback.
""")
    menu.pause()


def _hunt_credentials(menu, endpoint_id):
    credentials_api = getattr(menu.sdk, 'credentials', None)
    if credentials_api is None:
        return []
    try:
        credentials, _ = credentials_api.list(pages=1)
    except Exception as exc:
        _print_message(
            menu,
            f'Credential options unavailable: {exc}',
            'warning',
        )
        return []

    supported = []
    for credential in credentials:
        credential_type = _value(credential, 'type', 'credentialType')
        if credential_type == 'web-auth':
            supported.append(credential)
            continue
        if credential_type != 'active-directory':
            continue
        endpoint_ids = _value(credential, 'endpointIds', 'endpoint_ids') or []
        account_key = _value(credential, 'accountKey', 'account_key')
        if endpoint_id in endpoint_ids or (not endpoint_ids and account_key == endpoint_id):
            supported.append(credential)
    return supported


def launch_hunt(menu, endpoint, args):
    try:
        options = _parse_launch_args(args)
        if options['help']:
            show_hunt_help(menu)
            return
        objective = options['prompt'] or Prompt.ask('  Hunt objective').strip()
        scopes = [
            resolve_entity_reference(
                menu.sdk,
                value,
                'asset',
                interactive=True,
                console=menu.console,
            )
            for value in options['scopes']
        ]
        if not objective:
            raise ValueError('hunt objective is required')
        if not scopes:
            candidates, next_scope_page = menu.sdk.assets.list_hunt_scope(
                agent='hannibal',
                internal=True,
                pages=1,
            )
            scopes = select_entity_keys(
                menu.console,
                candidates,
                title='Select internal Hunt targets',
                search_entities=lambda query, page: menu.sdk.assets.list_hunt_scope(
                    agent='hannibal',
                    internal=True,
                    search=query,
                    page=int(page or 0),
                    pages=1,
                ),
                next_offset=next_scope_page,
            )
        if not scopes:
            raise ValueError('at least one internal Hunt target is required')
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return

    endpoint_id = agent_display_id(endpoint)
    endpoint_name = endpoint.hostname or endpoint_id
    endpoint_state = 'online' if endpoint.is_online else 'offline'
    used_wizard = False
    if not options['yes']:
        launch_config, used_wizard = configure_hunt_launch(
            menu.console,
            {
                'prompt': objective,
                'aggressiveness': options['aggressiveness'],
                'guardrails': options['guardrails'],
                'finish_criteria': options['finish_criteria'],
                'expires': options['expires'],
                'custom_tag': options['custom_tag'],
                'model_tier': options['model_tier'],
                'credential_ids': list(options['credential_ids']),
            },
            scopes,
            f'{endpoint_name} ({endpoint_id}, {endpoint_state})',
            _hunt_credentials(menu, endpoint_id),
        )
        if used_wizard and launch_config is None:
            menu.console.print('  Cancelled')
            menu.pause()
            return
        if used_wizard:
            objective = launch_config['prompt']
            options.update(launch_config)

    confirmation = Text(
        f'Run this AI Hunt through {_safe(endpoint_name)} '
        f'({_safe(endpoint_id)}, {endpoint_state})? If unavailable, the Hunt '
        'waits without external compute fallback'
    )
    if (
        not options['yes']
        and not used_wizard
        and not Confirm.ask(confirmation, default=False)
    ):
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
            finish_criteria=options['finish_criteria'],
            user_guardrails=options['guardrails'],
            custom_tag=options['custom_tag'],
            model_tier_override=options['model_tier'],
            credential_ids=options['credential_ids'] or None,
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
    show_workflows = '--workflows' in args
    hunt_args = [arg for arg in args if arg != '--workflows']
    hunt = _get_selected_hunt(menu, endpoint, hunt_args)
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
        (
            'Credentials',
            ', '.join(_value(hunt, 'credentialIds', 'credential_ids') or []) or '—',
        ),
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

    if show_workflows:
        try:
            runs, _ = menu.sdk.hunts.list_workflow_runs(_hunt_id(hunt))
        except Exception as exc:
            _print_message(
                menu,
                f'Workflow status unavailable: {exc}',
                'warning',
            )
        else:
            menu.console.print()
            browse_hunt_workflows(menu.console, runs)
    menu.pause()


def show_hunt_findings(menu, endpoint, args):
    try:
        options = _parse_findings_args(args)
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return
    if _get_selected_hunt(menu, endpoint, [options['hunt_id']]) is None:
        return

    try:
        findings, _ = menu.sdk.hunts.list_findings(
            options['hunt_id'],
            pages=10000 if options['all'] else 1,
        )
        findings = filter_hunt_findings(
            findings,
            status=options['status'],
            severity=options['severity'],
        )
        if options['details'] or options['evidence'] != 'off':
            findings = [
                menu.sdk.risks.get(
                    finding.get('key'),
                    details=True,
                    evidence=options['evidence'],
                )
                for finding in findings
                if finding.get('key')
            ]
    except Exception as exc:
        _print_message(menu, f'Unable to load Hunt vulnerabilities: {exc}', 'error')
    else:
        menu.console.print(build_hunt_findings(
            findings,
            show_details=options['details'] or options['evidence'] != 'off',
        ))
    menu.pause()


def manage_hunt_memory(menu, endpoint, args):
    try:
        options = _parse_memory_args(args)
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return
    hunt_id = options['hunt_id']
    if _get_selected_hunt(menu, endpoint, [hunt_id]) is None:
        return

    try:
        if options['delete']:
            if not options['yes'] and not Confirm.ask(
                f'Delete Hunt memory item {options["item"]!r}?',
                default=False,
            ):
                menu.console.print('  Cancelled')
                menu.pause()
                return
            menu.sdk.hunts.delete_memory(hunt_id, options['item'])
            _print_message(menu, f'Deleted memory item {options["item"]}.', 'success')
        elif options['content'] is not None:
            menu.sdk.hunts.save_memory(
                hunt_id,
                options['item'],
                options['content'],
            )
            _print_message(menu, f'Saved memory item {options["item"]}.', 'success')
        elif options['item']:
            content = menu.sdk.hunts.get_memory(hunt_id, options['item'])
            menu.console.print(build_hunt_memory_item(options['item'], content))
        else:
            items, _ = menu.sdk.hunts.list_memory(hunt_id)
            menu.console.print(build_hunt_memory(items))
    except Exception as exc:
        _print_message(menu, f'Unable to manage Hunt memory: {exc}', 'error')
    menu.pause()


def show_hunt_log(menu, endpoint, args):
    try:
        options = _parse_log_args(args)
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return
    hunt_id = options['hunt_id']
    if _get_selected_hunt(menu, endpoint, [hunt_id]) is None:
        return

    try:
        content = menu.sdk.hunts.get_log(hunt_id)
        menu.console.print(build_hunt_log(content))
        while options['follow']:
            time.sleep(options['interval'])
            latest = menu.sdk.hunts.get_log(hunt_id)
            if latest == content:
                continue
            update = latest[len(content):] if latest.startswith(content) else latest
            content = latest
            menu.console.print(build_hunt_log(update))
    except KeyboardInterrupt:
        menu.console.print('  Stopped following Hunt log.')
    except Exception as exc:
        _print_message(menu, f'Unable to load Hunt log: {exc}', 'error')
    menu.pause()


def chat_hunt(menu, endpoint, args):
    try:
        options = _parse_chat_args(args)
    except ValueError as exc:
        _print_message(menu, f'Error: {exc}', 'error')
        menu.pause()
        return

    hunt = _get_selected_hunt(menu, endpoint, [options['hunt_id']])
    if hunt is None:
        return

    try:
        conversations, _ = menu.sdk.hunts.list_conversations(
            options['hunt_id']
        )
        selected = select_hunt_conversation(
            conversations,
            requested_id=options['conversation_id'],
            require_active=bool(options['message']),
        )
        selected_id = selected.get('uuid') or selected.get('id')
        if options['message']:
            menu.sdk.conversations.send_message(
                selected_id,
                options['message'],
            )
        transcript = menu.sdk.conversations.get(selected_id)
    except Exception as exc:
        _print_message(menu, f'Unable to open Hunt chat: {exc}', 'error')
        menu.pause()
        return

    menu.console.print(build_hunt_chat(conversations, selected, transcript))
    if options['message']:
        _print_message(
            menu,
            'Guidance queued for the running Hunt iteration.',
            'success',
        )
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
        'expires': DEFAULT_HUNT_DURATION_HOURS,
        'scope_level': 'normal',
        'aggressiveness': 'balanced',
        'finish_criteria': DEFAULT_FINISH_CRITERIA,
        'guardrails': '',
        'custom_tag': '',
        'model_tier': None,
        'credential_ids': [],
        'yes': False,
        'help': False,
    }
    value_options = {
        '-p': 'prompt', '--prompt': 'prompt',
        '-s': 'scope', '--scope': 'scope',
        '-e': 'expires', '--expires': 'expires',
        '--scope-level': 'scope_level',
        '--aggressiveness': 'aggressiveness',
        '--finish-criteria': 'finish_criteria',
        '--guardrails': 'guardrails',
        '--custom-tag': 'custom_tag',
        '--model-tier': 'model_tier',
        '--credential': 'credential',
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
        elif destination == 'credential':
            options['credential_ids'].append(value)
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
    if options['model_tier'] not in (None, 'experimental'):
        raise ValueError('--model-tier must be experimental')
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


def _parse_findings_args(args):
    options = {
        'hunt_id': None,
        'status': None,
        'severity': None,
        'details': False,
        'evidence': 'off',
        'all': False,
    }
    index = 0
    value_options = {
        '--status': 'status',
        '--severity': 'severity',
        '--evidence': 'evidence',
    }
    while index < len(args):
        token = args[index]
        if token in ('--details', '--all'):
            options[token.removeprefix('--')] = True
            index += 1
        elif token in value_options:
            if index + 1 >= len(args):
                raise ValueError(f'{token} requires a value')
            options[value_options[token]] = args[index + 1].lower()
            index += 2
        elif token.startswith('-'):
            raise ValueError(f'unknown option: {token}')
        elif options['hunt_id'] is None:
            options['hunt_id'] = token
            index += 1
        else:
            raise ValueError(f'unexpected argument: {token}')

    if not options['hunt_id']:
        raise ValueError('a Hunt ID is required')
    severities = ('critical', 'high', 'medium', 'low', 'info', 'exposure')
    if options['severity'] and options['severity'] not in severities:
        raise ValueError(f'--severity must be one of {", ".join(severities)}')
    if options['evidence'] not in ('off', 'basic', 'full'):
        raise ValueError('--evidence must be off, basic, or full')
    return options


def _parse_memory_args(args):
    options = {
        'hunt_id': None,
        'item': None,
        'content': None,
        'delete': False,
        'yes': False,
    }
    index = 0
    while index < len(args):
        token = args[index]
        if token in ('--delete', '-y', '--yes'):
            key = 'delete' if token == '--delete' else 'yes'
            options[key] = True
            index += 1
        elif token in ('--item', '--content'):
            if index + 1 >= len(args):
                raise ValueError(f'{token} requires a value')
            options[token.removeprefix('--')] = args[index + 1]
            index += 2
        elif token.startswith('-'):
            raise ValueError(f'unknown option: {token}')
        elif options['hunt_id'] is None:
            options['hunt_id'] = token
            index += 1
        else:
            raise ValueError(f'unexpected argument: {token}')

    if not options['hunt_id']:
        raise ValueError('a Hunt ID is required')
    if options['content'] is not None and options['delete']:
        raise ValueError('--content and --delete cannot be combined')
    if (options['content'] is not None or options['delete']) and not options['item']:
        raise ValueError('--item is required when modifying memory')
    return options


def _parse_log_args(args):
    options = {'hunt_id': None, 'follow': False, 'interval': 5.0}
    index = 0
    while index < len(args):
        token = args[index]
        if token == '--follow':
            options['follow'] = True
            index += 1
        elif token == '--interval':
            if index + 1 >= len(args):
                raise ValueError('--interval requires a value')
            try:
                options['interval'] = float(args[index + 1])
            except ValueError as exc:
                raise ValueError('--interval must be a number') from exc
            index += 2
        elif token.startswith('-'):
            raise ValueError(f'unknown option: {token}')
        elif options['hunt_id'] is None:
            options['hunt_id'] = token
            index += 1
        else:
            raise ValueError(f'unexpected argument: {token}')
    if not options['hunt_id']:
        raise ValueError('a Hunt ID is required')
    if options['interval'] < 1:
        raise ValueError('--interval must be at least 1 second')
    return options


def _parse_chat_args(args):
    options = {
        'hunt_id': None,
        'conversation_id': None,
        'message': None,
    }
    index = 0
    while index < len(args):
        token = args[index]
        if token in ('--conversation', '--message'):
            if index + 1 >= len(args):
                raise ValueError(f'{token} requires a value')
            key = 'conversation_id' if token == '--conversation' else 'message'
            options[key] = args[index + 1]
            index += 2
        elif token.startswith('-'):
            raise ValueError(f'unknown option: {token}')
        elif options['hunt_id'] is None:
            options['hunt_id'] = token
            index += 1
        else:
            raise ValueError(f'unexpected argument: {token}')

    if not options['hunt_id']:
        raise ValueError('a Hunt ID is required')
    if options['message'] is not None and not options['message'].strip():
        raise ValueError('guidance message is required')
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
