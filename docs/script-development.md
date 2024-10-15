# Scripting the CLI

The CLI has a scripting engine for you to extend the CLI in a few steps without updating
the CLI codebase. The scripting engine works by loading scripts from any directories where
you store your scripts. It makes them available as commands under the `script` group. You
can list all the script commands by:

```zsh
praetorian chariot script --help
```

To add your own extensions to the CLI, set `PRAETORIAN_SCRIPTS_PATH` environment variable
to point to directories where you store your scripts.

The code snippet below is an example that runs an nmap scan on a host. It further adds
the open ports to your account on Chariot using the SDK.

The main logic is in `nmap_command`. This function uses Click decorators to register itself
to the CLI and define command line arguments.

Equally important is the `register` function. It must take one argument `script_group` and
use the `add_command` function to register the `nmap_command` function with the CLI.

```python
@click.command('nmap')
@click.argument('host', required=True)
@cli_handler
def nmap_command(sdk, host):
    """ An nmap script for scanning a host.

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
        print('No live host found.')


def register(script_group: click.MultiCommand):
    script_group.add_command(nmap_command)
```

## Debugging

The CLI skips loading scripts that have compilation errors. If you script does not
appear in `praetorian chariot script --help`, run the CLI with the `--debug` flag to
see the compilation errors.

## Go further

- The full example script with comments and notes is available here:
  [nmap-example.py](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/commands/nmap-example.py)
- Click has extensive support for command line arguments. You can use all of its functionality. See
  [Click's documentation](https://click.palletsprojects.com/en/8.1.x/parameters/) for full details.


  



