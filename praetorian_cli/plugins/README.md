## Developing plugin commands and scripts

The CLI has a plugin engine for you to extend the CLI without changing its internals. Your scripts
and commands are imported to the CLI context so it has full and authenticated access to the SDK.

There are two types plugins. Which one to use depends on the functionality you are adding:
- **Scripts**: a script that carries out additional processing of the output of an existing CLI
  command. An example is a script that invokes TruffleHog to further validate the secrets in exposure risks.
- **Commands**: a command that executes an end-to-end function. An example is a command that
  runs a Nessus scan and injects the scan results into Chariot.

  
### Plugin scripts
A plugin script does additional processing of the output of a CLI command.  It is invoked using
the `--plugin` option of a `list`, `search`, or `get` command. To get imported to the CLI
context and be invoked, the script needs to implement a `process` function that takes 4 arguments:
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

Here is a sample output of the example plugin script:

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
- Use the authenticated session in `controller` to further issue API calls to operate
  on the data.

Explore scripts that are shipped with the CLI for real-world usage, such as
[`list_assets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plguins/scripts/list_assets.py)
and
[`validate_secrets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/scripts/validate_secrets.py)



### Plugin commands
You can add full end-to-end functionality as CLI commands to run complex workflows with ease.
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
