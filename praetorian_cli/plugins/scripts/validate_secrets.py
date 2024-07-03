"""
This script is used to validate secrets using TruffleHog.
It is used with the 'list risks --details' command.

Example usage:

  praetorian chariot list risks --details --plugin validate_secrets

Prerequisites:

  TruffleHog version 3.78.0 or above

"""
import json
import subprocess

from praetorian_cli.plugins.utils import requires


@requires('trufflehog',
          'This script requires TruffleHog. See instructions at https://github.com/trufflesecurity/trufflehog.')
def process(controller, cmd, cli_kwargs, output):
    # Verify the upstream CLI command is compatible with the script
    if cmd['action'] != 'list' and cmd['type'] != 'risks':
        print("This script only works with the 'list risks' command.")
        return

    # Validate CLI output contains the required data
    if not cli_kwargs['details']:
        print("Please use --details option to get the required output.")
        return

    risks = json.loads(output).get('data', [])
    path = 'secrets/'
    print("Downloading secrets for validation...")
    for risk in risks:
        if risk['source'] == 'secrets':
            try:
                file_path = (controller.download(f"{risk['dns']}/{risk['name']}", path))
            except Exception as e:
                print(f"Error downloading {risk['dns']}/{risk['name']}: {e}")
                continue

            validate_secrets(file_path, risk['key'])


def validate_secrets(path, risk_key):
    result = subprocess.run(['trufflehog', 'filesystem', path,
                             '--only-verified', '--json'], capture_output=True)
    validated = {}
    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
            if not 'Verified' in data.keys() or not data['Verified']:
                continue
            validated[risk_key] = ([data['Raw'], data['ExtraData']])
        except json.JSONDecodeError:
            continue

    # Print the validated secrets along with the risk key
    for key, value in validated.items():
        print(f"Risk: {key}")
        print(f"{value[0]}\n{json.dumps(value[1], indent=4)}")
