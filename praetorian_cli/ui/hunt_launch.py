import sys
from io import StringIO

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from praetorian_cli.ui.hunt_defaults import DEFAULT_GUARDRAILS


AGGRESSIVENESS_OPTIONS = (
    (
        'cautious',
        'Cautious',
        'Narrow iterations. Confirms one vulnerability at a time and does not follow leads to related infrastructure.',
    ),
    (
        'balanced',
        'Balanced',
        'Default posture. Follows high-value leads and pivots to related infrastructure when the evidence warrants it.',
    ),
    (
        'aggressive',
        'Aggressive',
        'Deep multi-hop pivots and attack chaining. Records confirmed chains as attack graphs.',
    ),
)
DURATION_OPTIONS = (
    (8, '8 hours', 'Focused, short-duration assessment.'),
    (24, '24 hours', 'Default duration for a standard Hunt.'),
    (48, '48 hours', 'Extended assessment across a broader target set.'),
    (72, '72 hours', 'Maximum duration for long-running exploration.'),
)
MODEL_OPTIONS = (
    (None, 'Standard', 'Use the standard production model routing.'),
    (
        'experimental',
        'Experimental',
        'Use experimental model routing. Requires super-admin authorization.',
    ),
)


class HuntLaunchConfigurator:
    """Editable launch configuration for the fullscreen Hunt wizard."""

    fields = (
        ('prompt', 'Mandate', 'text'),
        ('targets', 'Targets', 'readonly'),
        ('endpoint', 'Endpoint', 'readonly'),
        ('ad_credential', 'Active Directory credential', 'choice'),
        ('web_auth_credential', 'Web authentication credential', 'choice'),
        ('aggressiveness', 'Aggressiveness', 'choice'),
        ('guardrails', 'Additional guardrails', 'text'),
        ('finish_criteria', 'Finish criteria', 'text'),
        ('expires', 'Duration', 'choice'),
        ('custom_tag', 'Finding tag', 'text'),
        ('model_tier', 'Model tier', 'choice'),
        ('launch', 'Launch Hunt', 'action'),
    )

    def __init__(self, config, targets, endpoint, credentials=None):
        self.config = dict(config)
        self.targets = list(targets)
        self.endpoint = endpoint
        self.credentials = [
            credential for credential in credentials or []
            if _credential_id(credential)
            and _credential_type(credential) in ('active-directory', 'web-auth')
        ]
        configured_ids = list(self.config.get('credential_ids') or [])
        self.selected_credentials = {}
        for credential in self.credentials:
            credential_id = _credential_id(credential)
            if credential_id in configured_ids:
                self.selected_credentials[_credential_type(credential)] = credential_id
        known_ids = {_credential_id(credential) for credential in self.credentials}
        self.unresolved_credential_ids = [
            credential_id for credential_id in configured_ids
            if credential_id not in known_ids
        ]
        self.cursor = 0
        self.editing = False
        self.edit_value = ''
        self.original_value = ''
        self.status = ''

    @property
    def field(self):
        return self.fields[self.cursor]

    def move(self, delta):
        if self.editing:
            return
        self.cursor = min(max(self.cursor + delta, 0), len(self.fields) - 1)
        self.status = ''

    def activate(self):
        name, _label, kind = self.field
        if kind == 'choice':
            self.cycle(1)
            return None
        if kind == 'text':
            self.editing = True
            self.original_value = str(self.config.get(name) or '')
            self.edit_value = self.original_value
            self.status = 'Editing · Enter saves · Esc cancels · Ctrl+U clears'
            return None
        if kind == 'action':
            return self.confirmed_config()
        self.status = 'This value is determined by the selected endpoint and targets.'
        return None

    def cycle(self, direction):
        name, _label, kind = self.field
        if kind != 'choice' or self.editing:
            return
        options = self._choice_options(name)
        values = [option[0] for option in options]
        credential_type = {
            'ad_credential': 'active-directory',
            'web_auth_credential': 'web-auth',
        }.get(name)
        current = (
            self.selected_credentials.get(credential_type)
            if credential_type
            else self.config.get(name)
        )
        try:
            index = values.index(current)
        except ValueError:
            index = 0
        selected = values[(index + direction) % len(values)]
        if credential_type:
            if selected is None:
                self.selected_credentials.pop(credential_type, None)
            else:
                self.selected_credentials[credential_type] = selected
        else:
            self.config[name] = selected
        self.status = self._choice_description(name)

    def append_edit(self, value):
        if self.editing:
            self.edit_value += value

    def backspace_edit(self):
        if self.editing:
            self.edit_value = self.edit_value[:-1]

    def clear_edit(self):
        if self.editing:
            self.edit_value = ''

    def save_edit(self):
        if not self.editing:
            return
        name, _label, _kind = self.field
        value = self.edit_value.strip()
        if name == 'prompt' and not value:
            self.status = 'The Hunt mandate cannot be empty.'
            return
        self.config[name] = value
        self.editing = False
        self.status = 'Saved.'

    def cancel_edit(self):
        self.editing = False
        self.edit_value = self.original_value
        self.status = 'Edit cancelled.'

    def confirmed_config(self):
        if not str(self.config.get('prompt') or '').strip():
            self.status = 'The Hunt mandate cannot be empty.'
            return None
        config = dict(self.config)
        config['credential_ids'] = [
            *self.selected_credentials.values(),
            *self.unresolved_credential_ids,
        ]
        return config

    def value(self, name):
        if name == 'targets':
            return f'{len(self.targets)} selected'
        if name == 'endpoint':
            return self.endpoint
        if name in ('ad_credential', 'web_auth_credential'):
            credential_type = (
                'active-directory' if name == 'ad_credential' else 'web-auth'
            )
            current = self.selected_credentials.get(credential_type)
            return next(
                (
                    label for value, label, _description
                    in self._choice_options(name)
                    if value == current
                ),
                'None',
            )
        if name in ('aggressiveness', 'expires', 'model_tier'):
            current = self.config.get(name)
            return next(
                (
                    label for value, label, _description
                    in self._choice_options(name)
                    if value == current
                ),
                str(current or '—'),
            )
        if name == 'launch':
            return 'Press Enter to launch'
        value = str(self.config.get(name) or '')
        return _preview(value) if value else '—'

    def description(self):
        name, _label, kind = self.field
        if self.editing:
            return 'Type the replacement value. Enter saves; Escape cancels.'
        if name == 'prompt':
            return 'The primary objective and mandate for Hannibal.'
        if name == 'targets':
            return '\n'.join(_target_label(target) for target in self.targets[:12])
        if name == 'endpoint':
            return 'All target-network work remains pinned to this Aegis endpoint.'
        if name in ('ad_credential', 'web_auth_credential'):
            return self._choice_description(name)
        if name == 'guardrails':
            return (
                'Additional restrictions are applied on top of this enforced baseline:\n\n'
                + DEFAULT_GUARDRAILS
            )
        if name == 'finish_criteria':
            return 'Conditions that allow Hannibal to end the Hunt early.'
        if name == 'custom_tag':
            return 'Optional tag stamped onto findings created by this Hunt.'
        if kind == 'choice':
            return self._choice_description(name)
        if kind == 'action':
            return 'Review the configuration above, then press Enter to launch.'
        return ''

    def _choice_options(self, name):
        if name == 'ad_credential':
            return self._credential_options('active-directory')
        if name == 'web_auth_credential':
            return self._credential_options('web-auth')
        if name == 'aggressiveness':
            return AGGRESSIVENESS_OPTIONS
        if name == 'expires':
            return DURATION_OPTIONS
        if name == 'model_tier':
            return MODEL_OPTIONS
        return ()

    def _credential_options(self, credential_type):
        options = [(None, 'None', 'Do not attach this credential type.')]
        for credential in self.credentials:
            if _credential_type(credential) != credential_type:
                continue
            credential_id = _credential_id(credential)
            label = str(
                credential.get('name')
                or credential.get('label')
                or credential_id
            )
            resource = str(
                credential.get('domain')
                or credential.get('accountKey')
                or credential.get('account_key')
                or 'compatible targets'
            )
            options.append((
                credential_id,
                label,
                f'{credential_type} · {resource} · ID {credential_id}',
            ))
        return tuple(options)

    def _choice_description(self, name):
        if name == 'ad_credential':
            current = self.selected_credentials.get('active-directory')
        elif name == 'web_auth_credential':
            current = self.selected_credentials.get('web-auth')
        else:
            current = self.config.get(name)
        return next(
            (
                description for value, _label, description
                in self._choice_options(name)
                if value == current
            ),
            '',
        )


def configure_hunt_launch(
    console,
    config,
    targets,
    endpoint,
    credentials=None,
):
    """Run the launch wizard in a TTY and return (config, used_wizard)."""
    if not _supports_fullscreen_wizard():
        return dict(config), False
    configurator = HuntLaunchConfigurator(
        config,
        targets,
        endpoint,
        credentials,
    )
    return _run_hunt_launch_wizard(console, configurator), True


def _supports_fullscreen_wizard():
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def _run_hunt_launch_wizard(console, configurator):
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    key_bindings = KeyBindings()

    @key_bindings.add('up')
    @key_bindings.add('s-tab')
    def _up(event):
        configurator.move(-1)

    @key_bindings.add('down')
    @key_bindings.add('tab')
    def _down(event):
        configurator.move(1)

    @key_bindings.add('left')
    def _previous_choice(event):
        configurator.cycle(-1)

    @key_bindings.add('right')
    @key_bindings.add(' ')
    def _next_choice(event):
        if configurator.editing:
            configurator.append_edit(' ')
        else:
            configurator.cycle(1)

    @key_bindings.add('enter')
    def _activate(event):
        if configurator.editing:
            configurator.save_edit()
            return
        result = configurator.activate()
        if result is not None:
            event.app.exit(result=result)

    @key_bindings.add('backspace')
    def _backspace(event):
        configurator.backspace_edit()

    @key_bindings.add('c-u')
    def _clear(event):
        configurator.clear_edit()

    @key_bindings.add('c-s')
    def _launch(event):
        if configurator.editing:
            configurator.save_edit()
            return
        result = configurator.confirmed_config()
        if result is not None:
            event.app.exit(result=result)

    @key_bindings.add('q')
    def _quit(event):
        if configurator.editing:
            configurator.append_edit('q')
        else:
            event.app.exit(result=None)

    @key_bindings.add('escape')
    def _escape(event):
        if configurator.editing:
            configurator.cancel_edit()
        else:
            event.app.exit(result=None)

    @key_bindings.add('c-c')
    def _cancel(event):
        event.app.exit(result=None)

    @key_bindings.add(Keys.Any)
    def _edit(event):
        if configurator.editing and event.data.isprintable():
            configurator.append_edit(event.data)

    def display():
        output = StringIO()
        render_console = Console(
            file=output,
            force_terminal=True,
            width=max(90, getattr(console, 'width', 90)),
        )
        render_console.print(
            '↑/↓ move  ←/→ or SPACE change  ENTER edit/select  '
            'Ctrl+S launch  ESC cancel',
            style='dim',
        )
        render_console.print(_configuration_table(configurator))
        render_console.print(_configuration_detail(configurator))
        if configurator.status:
            render_console.print(configurator.status, style='yellow')
        return ANSI(output.getvalue())

    application = Application(
        layout=Layout(Window(content=FormattedTextControl(display))),
        key_bindings=key_bindings,
        full_screen=True,
    )
    return application.run()


def _configuration_table(configurator):
    table = Table(
        title=Text('Configure Internal Hunt', style='bold magenta'),
        box=box.ROUNDED,
        border_style='magenta',
        expand=True,
        header_style='bold',
    )
    table.add_column('', width=3)
    table.add_column('SETTING', width=23)
    table.add_column('VALUE', min_width=40, ratio=1)
    for index, (name, label, kind) in enumerate(configurator.fields):
        selected = index == configurator.cursor
        marker = Text('▶' if selected else ' ', style='bold cyan')
        value = configurator.value(name)
        style = 'bold green' if kind == 'action' else ('bold white' if selected else 'white')
        table.add_row(marker, Text(label, style=style), Text(value, style=style))
    return table


def _configuration_detail(configurator):
    name, label, _kind = configurator.field
    if configurator.editing:
        body = Text(configurator.edit_value or ' ', style='white')
        body.append('█', style='cyan')
    else:
        body = Text(configurator.description() or '—')
    return Panel(
        body,
        title=Text(label, style='bold cyan'),
        border_style='cyan',
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _credential_id(credential):
    identifier = (
        credential.get('credentialId')
        or credential.get('credential_id')
        or credential.get('id')
        or credential.get('key')
        or ''
    )
    return str(identifier).rsplit('#', 1)[-1].strip()


def _credential_type(credential):
    return str(
        credential.get('type')
        or credential.get('credentialType')
        or ''
    ).strip()


def _target_label(target):
    if not isinstance(target, dict):
        return str(target)
    return str(
        target.get('dns')
        or target.get('name')
        or target.get('identifier')
        or target.get('key')
        or 'target'
    )


def _preview(value, limit=100):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= limit else value[:limit - 1] + '…'
