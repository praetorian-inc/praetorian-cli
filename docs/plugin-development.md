# Plugin development

The CLI has a plugin engine for you to easily extend the CLI in a few steps. 

To add your own command to the CLI, set `PRAETORIAN_SCRIPTS_PATH` environment variable to point to
directories where you store your scripts.

The CLI attempts to load every script that has the `register` function defined. All compatible
scripts will be added to the `plugin` group, which you can list by 

```zsh
praetorian chariot plugin --help
```

The code snippet below is a concrete example that runs an nmap scan on a host and add the open ports
to Chariot using the SDK.

The main logic is in `nmap_command`. This function uses Click decorators to register itself
to the CLI and define command line arguments.

Equally important is the `register` function. It must take one argument `plugin_group` and 
use the `add_command` function to register the `nmap_command` function with the CLI.


```python
@click.command('nmap')
@click.argument('host', required=True)
@cli_handler
def nmap_command(sdk, host):
    """ An nmap plugin for scanning a host.

        HOST is the host you want to scan. It can be a hostname or an IP address.
    """

    print(f'Running nmap on {host}...')
    result = subprocess.run(['nmap', '-p22,80,443', host], capture_output=True, text=True)

    if 'Nmap scan report' in result.stdout:
        lines = result.stdout.split('\n')
        asset_key = f'#asset#{host}#{host}.'
        sdk.add('asset', dict(name=host, dns=host))
        print(f'Added asset {asset_key}')
        for l in lines[5:]:
            match = re.match('^(\d+)/[a-z]+\s+open\s+([a-z]+)$', l)
            if match:
                (port, protocol) = match.groups()
                sdk.add('attribute', dict(key=asset_key, name=protocol, value=port))
                print(f'Added attribute for open port {port} running {protocol}.')
    else:
        print("No live host found.")


def register(plugin_group: click.MultiCommand):
    plugin_group.add_command(nmap_command)

```


## Go further

- The full example script with comments and notes is available here:
  [nmap-example.py](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/commands/nmap-example.py)
- Click has extensive support for command line arguments. You can use all of its functionality. See
  [Click's documentation](https://click.palletsprojects.com/en/8.1.x/parameters/) for full details.


  



