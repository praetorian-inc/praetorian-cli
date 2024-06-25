## Contributing scripts and plugins

The CLI has a script engine for you to extend the CLI without changing its internals. Your script
is imported to the CLI context so it has full and authenticated access to the SDK.

### Adding plugins

- Write a script that implements a `process` function taking 4 arguments:
    - `controller`: An authenticated session of the Praetorian API.
    - `cmd`: This dictionary contains information about the executed CLI command, including the product, action, and
      type.
    - `cli_kwargs`: This dictionary contains the additional options the user provided to the CLI.
    - `output`: This is the raw output of the CLI.
- Add the `@plugins` decorator to the commands you would like to extend with plugins.

Try out
the [`hello-world`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/hello-world.py)
plugin:

 ```zsh
praetorian chariot list seeds --plugin hello-world
```

Here is a sample output of the hello-world plugin:

```
Entering the process() function. It received 4 positional arguments. Inspecting them:

username = test_user@praetorian.com.

cmd = {'product': 'chariot', 'action': 'list', 'type': 'seeds'}.

cli_kwargs = {'details': False, 'filter': '', 'page': 'no', 'offset': ''}.

output =
#seed#example.com#example.com

Exiting the process() function
```

A typical script uses the arguments in the following manners:

- Check for input correctness using information in `cmd` and `cli_kwargs`.
- Parse the CLI `output` to extract relevant data.
- Use the authenticated session in `controller` to further issue API calls to operate
  on the data.

Explore existing plugins
like [`list-assets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/list-assets.py)
and
[`validate-secrets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/validate-secrets.py)
for reference.

### Adding scripts as commands

You can add standalone scripts as CLI commands to run complex workflows with ease.
Register them
in [handlers/run.py](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/handlers/run.py) as a new
command.

Snippet to register a new command called `hello` which runs
the [`hello_run`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/handlers/run.py) script:

```python
@run.command('hello')
@click.argument('args', nargs=-1)
@click.option('--kwargs', '-k', multiple=True, type=(str, str), help="Key-value pairs for the plugin")
@click.option('--strings', '-s', multiple=True, help="Multiple strings")
@cli_handler
def hello(controller, args, kwargs, strings):
    """Run the hello plugin"""
    hello_run.hello_function(controller, args, kwargs, strings)
```
