"""
For developers:
You can use this as a template for writing new CLI scripts.

How to use:

  1. Install the latest version of praetorian-cli

  2. Set PRAETORIAN_SCRIPTS_PATH environment variable to point to the directory
     where this script is located

  3. Run it:
     `praetorian chariot script --help`
     `praetorian chariot script nmap-example --help`
     `praetorian chariot script nmap-example scanme.nmap.org`

"""
import re
import subprocess

# You have to have the following two import statements at the minimum.
import click

from praetorian_cli.handlers.cli_decorators import cli_handler


# The nmap_command() function is the entry point to the command.
#
# In this example, the command takes one argument from the user, the hostname,
# and runs nmap against it to check for open ports in 22, 80, and 443.
#
# The scripting engine passes the arguments and options from your users to this function.
# The engine handles the plumbing of Click for you.
#
# Several things you need to follow for this to work:
#   1. Use @click.command() to register the command name you want.
#   2. You need to add the @cli_handler decorator.
#   3. You can use any @click functions for managing the command line arguments and options.
#   4. The first argument has to be`sdk`. This is the reference to the SDK with an
#      authenticated Chariot session.
#   5. The rest of arguments are Click arguments, in order.
@click.command('nmap-example')
@click.argument('host', required=True)
@cli_handler
def nmap_command(sdk, host):
    """ An nmap script for scanning a host

        HOST is the host you want to scan. It can be a hostname or an IP address.
    """

    print(f'Running nmap on {host}...')
    result = subprocess.run(['nmap', '-p22,80,443', host], capture_output=True, text=True)

    # Process the result from nmap and add asset and attributes if the asset
    # is live.
    if 'Nmap scan report' in result.stdout:
        lines = result.stdout.split('\n')
        asset_key = f'#asset#{host}#{host}.'
        sdk.add('asset', dict(name=host, dns=host))
        print(f'Added asset {asset_key}')
        for l in lines[5:]:
            match = re.match(r'^(\d+)/[a-z]+\s+open\s+([a-z]+)$', l)
            if match:
                (port, protocol) = match.groups()
                sdk.add('attribute', dict(key=asset_key, name=protocol, value=port))
                print(f'Added attribute for open port {port} running {protocol}.')
    else:
        print("No live host found.")


# The register() function has to be defined in this file. It is called by the CLI
# to register your command under the script group.
def register(script_group: click.MultiCommand):
    script_group.add_command(nmap_command)
