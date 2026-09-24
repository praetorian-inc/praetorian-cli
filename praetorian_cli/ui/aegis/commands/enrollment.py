import json
import re

from rich.box import MINIMAL
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ..constants import DEFAULT_COLORS


ENROLLMENT_ERROR_MESSAGES = {
    'invalid_request': 'Enrollment request was invalid. Enter the 8-character user code shown by the endpoint.',
    'expired_token': 'Invalid or expired enrollment code. Request a new code on the endpoint and try again.',
    'access_denied': (
        'Enrollment code cannot be approved for this account, was already approved for another account, '
        'or is no longer pending. Switch to the requested Guard account if needed.'
    ),
    'temporarily_unavailable': 'Enrollment approval is temporarily unavailable. Try again in a few minutes.',
    'authorization_pending': 'Enrollment is still waiting for operator approval.',
}


def handle_enrollment(menu, args):
    """Handle Aegis v2 enrollment commands."""
    if not args or args[0] in ('-h', '--help', 'help'):
        show_enrollment_help(menu)
        return

    subcommand = args[0].lower()
    if subcommand == 'inspect':
        inspect_enrollment(menu, args[1:])
    elif subcommand == 'approve':
        approve_enrollment(menu, args[1:])
    else:
        colors = getattr(menu, 'colors', DEFAULT_COLORS)
        menu.console.print(f"[{colors['error']}]Unknown enrollment subcommand: {subcommand}[/{colors['error']}]")
        show_enrollment_help(menu)


def show_enrollment_help(menu):
    menu.console.print("""
  Aegis v2 Enrollment Commands

  enrollment inspect <user-code>       Show pending enrollment details
  enrollment approve <user-code>       Inspect, confirm, and approve enrollment
  enrollment approve <user-code> --yes Approve after displaying details, without prompting

  The approval request sends only the enrollment user code; account and actor are derived by Guard.
""")
    menu.pause()


def inspect_enrollment(menu, args):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    try:
        user_code, _ = _parse_code_args(args, allow_yes=False)
        user_code = _prompt_user_code(user_code)
        pending = menu.sdk.aegis.inspect_enrollment(user_code)
    except ValueError as exc:
        menu.console.print(f"[{colors['error']}]Error: {exc}[/{colors['error']}]")
    except Exception as exc:
        menu.console.print(f"[{colors['error']}]{enrollment_error_message(exc)}[/{colors['error']}]")
    else:
        print_pending_enrollment(menu, pending)
    menu.pause()


def approve_enrollment(menu, args):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    try:
        user_code, yes = _parse_code_args(args, allow_yes=True)
        user_code = _prompt_user_code(user_code)
        pending = menu.sdk.aegis.inspect_enrollment(user_code)
    except ValueError as exc:
        menu.console.print(f"[{colors['error']}]Error: {exc}[/{colors['error']}]")
        menu.pause()
        return
    except Exception as exc:
        menu.console.print(f"[{colors['error']}]{enrollment_error_message(exc)}[/{colors['error']}]")
        menu.pause()
        return

    print_pending_enrollment(menu, pending)
    if not yes and not Confirm.ask('  Approve this enrollment?', default=False):
        menu.console.print('  Cancelled')
        menu.pause()
        return

    try:
        result = menu.sdk.aegis.approve_enrollment(user_code)
    except Exception as exc:
        menu.console.print(f"[{colors['error']}]{enrollment_error_message(exc)}[/{colors['error']}]")
    else:
        status = _approval_status(result)
        menu.console.print(f"  [{colors['success']}]Enrollment {status}[/{colors['success']}]")
    menu.pause()


def complete(menu, text, tokens):
    if len(tokens) <= 2:
        return [cmd for cmd in ('inspect', 'approve', 'help') if cmd.startswith(text)]
    if len(tokens) > 2 and tokens[1] == 'approve' and text.startswith('-'):
        return [option for option in ('--yes', '-y') if option.startswith(text)]
    return []


def pending_enrollment_lines(pending):
    return [f'{label}: {value}' for label, value in pending_enrollment_rows(pending)]


def pending_enrollment_rows(pending):
    return [
        ('Endpoint ID', _pending_value(pending, 'endpoint_id', 'endpointId')),
        ('Account', _pending_value(pending, 'account', 'Account')),
        ('Kind', _pending_value(pending, 'kind', 'Kind')),
        ('Version', _metadata_value(pending, 'version', 'Version')),
        ('Hostname', _metadata_value(pending, 'hostname', 'Hostname')),
        ('OS/Arch', _os_arch(pending)),
        ('Created', _pending_value(pending, 'created_at', 'createdAt')),
        ('Expires', _pending_value(pending, 'expires_at', 'expiresAt')),
    ]


def print_pending_enrollment(menu, pending):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    table = Table(
        title='Pending Aegis v2 Enrollment',
        show_header=False,
        border_style=colors['dim'],
        box=MINIMAL,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column('Field', style=f"bold {colors['primary']}", no_wrap=True)
    table.add_column('Value', style='white')
    for label, value in pending_enrollment_rows(pending):
        table.add_row(label, Text(str(value or 'N/A')))
    menu.console.print()
    menu.console.print(table)
    menu.console.print()


def enrollment_error_message(error):
    code = _extract_error_code(str(error))
    if code in ENROLLMENT_ERROR_MESSAGES:
        return ENROLLMENT_ERROR_MESSAGES[code]
    status = _extract_status(str(error))
    if status:
        return f'Enrollment request failed with HTTP {status}. Try again or re-run with --debug for details.'
    return 'Enrollment request failed. Try again or re-run with --debug for details.'


def _parse_code_args(args, allow_yes):
    yes = False
    positional = []
    for arg in args:
        if allow_yes and arg in ('-y', '--yes'):
            yes = True
        elif arg.startswith('-'):
            raise ValueError(f'Unknown option: {arg}')
        else:
            positional.append(arg)
    if len(positional) > 1:
        raise ValueError('expected one enrollment user code')
    return (positional[0] if positional else None), yes


def _prompt_user_code(user_code):
    if user_code:
        return user_code
    return Prompt.ask('  Enrollment user code').strip()


def _approval_status(result):
    if isinstance(result, dict):
        return str(result.get('status') or result.get('Status') or 'approved')
    return 'approved'


def _pending_value(pending, *keys):
    if not isinstance(pending, dict):
        return ''
    for key in keys:
        value = pending.get(key)
        if value not in (None, ''):
            return value
    return ''


def _metadata_value(pending, *keys):
    value = _pending_value(pending, *keys)
    if value:
        return value
    metadata = pending.get('metadata') or pending.get('Metadata') if isinstance(pending, dict) else {}
    if not isinstance(metadata, dict):
        return ''
    return _pending_value(metadata, *keys)


def _os_arch(pending):
    os_name = _metadata_value(pending, 'os', 'OS')
    arch = _metadata_value(pending, 'arch', 'Arch')
    if os_name and arch:
        return f'{os_name}/{arch}'
    return os_name or arch or ''


def _extract_error_code(message):
    match = re.search(r'Error:\s*(\{.*\})', message, flags=re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(1))
            code = payload.get('error')
            if isinstance(code, str):
                return code
        except json.JSONDecodeError:
            pass
    match = re.search(r'"error"\s*:\s*"([^"]+)"', message)
    if match:
        return match.group(1)
    for code in ENROLLMENT_ERROR_MESSAGES:
        if code in message:
            return code
    return ''


def _extract_status(message):
    match = re.search(r'\[(\d{3})\]', message)
    return match.group(1) if match else ''
