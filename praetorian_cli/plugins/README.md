## Developing plugin commands and scripts

The CLI has a plugin engine for you to easily extend the CLI in a few steps. Your plugins can have full and
authenticated access to CHariot platform using the SDK.

You can choose from two types plugins depending on your use-case:

- **Scripts**: To perform additional processing on the output of an existing CLI command. <br>For eg. A script that
  invokes TruffleHog to filter and validate secrets from a list of risks.
- **Commands**: To execute a workflow not supported by traditional CLI commands. <br>For eg. A command that
  runs a Nessus scan and injects the scan results into Chariot.

### Plugin scripts

A plugin script does additional processing of the output of a CLI command. It is invoked using
the `--plugin` option of a `list`, `search`, or `get` command.
<br>The script needs to implement a `process` function to be invoked. It needs to accept 4 arguments:

- `controller`: An authenticated session of the Praetorian API.
- `cmd`: This dictionary contains information about the executed CLI command, including the product, action, and
  type.
- `cli_kwargs`: This dictionary contains the additional options the user provided to the CLI.
- `output`: This is the raw output of the CLI.

Try the
[`example.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/scripts/example.py)
plugin script:

 ```zsh
praetorian chariot list seeds --plugin example
```

Here is a sample output from the command:

```
Entering the process() function. It received 4 positional arguments. Inspecting them:

username = test_user@praetorian.com.

cmd = {'product': 'chariot', 'action': 'list', 'type': 'seeds'}.

cli_kwargs = {'details': False, 'filter': '', 'page': 'no', 'offset': ''}.

output =
#seed#example.com#example.com
...

Exiting the process() function
```

A typical script uses the arguments in the following manners:

- Check for input correctness using information in `cmd` and `cli_kwargs`.
- Parse the CLI `output` to extract relevant data.
- Use the authenticated session in `controller` to issue API calls for further operations.

Explore scripts that are shipped with the CLI, such as
[`list_assets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plguins/scripts/list_assets.py)
and
[`validate_secrets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/scripts/validate_secrets.py)

### Plugin commands

You can add end-to-end functionalities as CLI commands to run complex workflows with ease.
<br>Register them
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
