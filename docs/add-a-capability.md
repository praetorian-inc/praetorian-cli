# Adding a Guard CLI Capability

This guide covers the pattern for adding a new CLI command backed by a Guard backend route.

## 1. Add the SDK entity method

Create or extend an entity in `praetorian_cli/sdk/entities/`.

```python
# praetorian_cli/sdk/entities/example.py

class Example:
    def __init__(self, api):
        self.api = api

    def list(self, **kwargs):
        return self.api.get('/example', params=kwargs)

    def create(self, name, config=None):
        body = {'name': name}
        if config:
            body['config'] = config
        return self.api.post('/example', body=body)
```

Wire it into the Chariot SDK in `praetorian_cli/sdk/chariot.py`:

```python
from praetorian_cli.sdk.entities.example import Example

class Chariot:
    def __init__(self, ...):
        ...
        self.example = Example(self.api)
```

## 2. Add the Click command handler

Create a handler in `praetorian_cli/handlers/`:

```python
# praetorian_cli/handlers/example.py

import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json

@chariot.group()
def example():
    """ Example commands """
    pass

@example.command()
@cli_handler
@click.option('--name', required=True, help='Name of the example')
def create(sdk, name):
    """ Create a new example """
    result = sdk.example.create(name)
    print_json(result)
```

Key conventions:
- Use `@chariot.group()` for command groups, `@chariot.command()` for standalone commands
- The `@cli_handler` decorator injects the `sdk` (Chariot instance) as the first argument
- Use `print_json()` for JSON output and `click.echo()` for plain text
- Destructive operations should require `--force` for non-interactive use

## 3. Register in main.py

Add the import to `praetorian_cli/main.py`:

```python
import praetorian_cli.handlers.example  # noqa: F401
```

This is not automatically picked up by the TUI console. If the command should also be available there, manually wire it into the TUI console's handlers dict and add it to the `CONSOLE_COMMANDS` list.

## 4. Update the parity registry

Edit `parity/routes.json` to mark the backend route(s) as `covered`:

```json
"/example": {
    "cli_command": "example create",
    "sdk_entity": "example.create",
    "gui": true,
    "disposition": "covered"
}
```

Run the parity check to verify: `python3 parity/check_parity.py`

## 5. Write tests

Create tests in `praetorian_cli/sdk/test/` using the `_invoke()` pattern:

```python
# praetorian_cli/sdk/test/test_example_cli.py

from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from praetorian_cli.handlers.chariot import chariot

def _invoke(*args):
    """Invoke a CLI command with a mocked Chariot SDK."""
    runner = CliRunner()
    with patch('praetorian_cli.sdk.chariot.Chariot') as MockChariot, \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        mock_sdk = MagicMock()
        MockChariot.return_value = mock_sdk
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
        )
    return result, mock_sdk

def test_create():
    result, sdk = _invoke('example', 'create', '--name', 'test')
    assert result.exit_code == 0
    sdk.example.create.assert_called_once_with('test')
```

The `_invoke()` helper patches `Chariot` at the constructor level because the `chariot` group callback constructs a real `Chariot` from `ctx.obj`. Passing `obj=mock_sdk` directly to `runner.invoke` does **not** work.
