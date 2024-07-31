"""
This script is used to automate common web enumeration tasks.
 
Example usage:

  praetorian chariot list attributes --details --plugin web_servers

Prerequisites:
    gowitness

"""
import time
import json
import subprocess

from praetorian_cli.plugins.utils import requires
from praetorian_cli.sdk.chariot import Chariot


@requires('gowitness',
          'This script requires gowitness. See instructions at https://github.com/sensepost/gowitness/wiki/Installation.')
def process(controller: Chariot, cmd, cli_kwargs, output):
    # Verify the upstream CLI command is compatible with the script
    if cmd['action'] != 'list' and cmd['type'] != 'attributes':
        print("This script only works with the 'list attributes' command.")
        return

    # Validate CLI output contains the required data
    if not cli_kwargs['details']:
        print("Please use --details option to get the required output.")
        return

    risks = json.loads(output).get('data', [])
    risks = filter(lambda x: x['key'].startswith('#attribute#http'), risks)
    websites = []
    for risk in risks:
        source = risk['source'].split('#')[2]
        name = risk['name']
        value = risk['value']
        websites.append(f"{name}://{source}:{value}")

    websites_file = open(f"websites-{int(time.time())}.txt", "w")
    websites_file.write("\n".join(websites))
    gowitness(websites_file.name)


def gowitness(file):
    subprocess.run(['gowitness', 'file', '-f', file])
