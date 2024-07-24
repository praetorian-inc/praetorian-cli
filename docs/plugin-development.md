## Developing plugin commands and scripts

The CLI has a plugin engine for you to easily extend the CLI in a few steps. Your plugins can have full and
authenticated access to Chariot platform using the SDK.

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
praetorian chariot list assets --plugin example
```

Here is a sample output from the command:

```
Entering the process() function. It received 4 positional arguments. Inspecting them:

username = test_user@praetorian.com.

cmd = {'product': 'chariot', 'action': 'list', 'type': 'assets'}.

cli_kwargs = {'details': False, 'filter': '', 'page': 'no', 'offset': ''}.

output =
#asset#example.com#example.com
...

Exiting the process() function
```

A typical script uses the arguments in the following manners:

- Check for input correctness using information in `cmd` and `cli_kwargs`.
- Parse the CLI `output` to extract relevant data.
- Use the authenticated session in `controller` to issue API calls for further operations.

Explore scripts that comes with the CLI, such as
[`list_assets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plguins/scripts/list_assets.py)
and
[`validate_secrets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/scripts/validate_secrets.py)

### Plugin commands

You can add end-to-end functionalities as CLI commands to run complex workflows with ease. There are two types of
plugin commands:

- **Static**: These are packaged as part of the CLI. 
- **Dynamic**: These are linked to the CLI at runtime. The CLI loads all plugin commands in the directories
  pointed in the `PRAETORIAN_SCRIPTS_PATH` environment variable.


#### Static plugin commands

To add a static plugin command, add the core logic in a new file at the
[`plugins/commands`](https://github.com/praetorian-inc/praetorian-cli/tree/peter/typos/praetorian_cli/plugins/commands)
directory. See
[`commands/example.py`](https://github.com/praetorian-inc/praetorian-cli/blob/peter/typos/praetorian_cli/plugins/commands/example.py)
for an Hello-world style example. This command demonstrates the use of Click's argument options and the easy access of the 
SDK by listing assets in your Chariot account. By writing your extension as a plugin command, you do not need to deal with
instantiation of the keychain and SDK.

To make your command avaiable in the CLI, register it
in [handlers/plugin.py](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/handlers/plugin.py) as a new
command, as in the code snippet below. Just like any Click command, you
can make full use of Click's support for arguments and options:

```python
@plugin.command('example')
@cli_handler
@click.argument('arg1', type=str)
@click.option('--opt1', default=None, help='A string option')
def example_command(sdk, arg1, opt1):
    """ An example plugin command, extending the CLI """
    example.run(sdk, arg1, opt1)
```

#### Dynamic plugin commands

Static plugin commands need to be merged into the open-source CLI for it to be available for others to use.
However, you may not want to merge yours because it can be something specific to your organization. Yet you
want to share with others in your organization.

Dynamic plugin commands facilitate this scenario.

Typically, an organzation maintains their own repository of internal plugins. The CLI has the 
ability to load them at run time and expose them as a first-class command under the `plugin` group.

To do that, set the `PRAETORIAN_SCRIPTS_PATH` environment variable. The CLI inspects all Python programs
in those directories and loads compatible plugins.





_Dynamic plugin commands_ are only supported in Linux and macOS systems.






