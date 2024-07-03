"""
This script retrieves the assets originating from a given asset. It retrieves
the asset from the CLI. In turn, it execute a search using the my() function
of the Chariot SDK to find all entities related to the asset. Finally, it
filters for the attributes entities of the 'seed' class, which store the
information of the assets originating from the given asset.

Example usage:

  praetorian chariot get asset '#asset#praetorian.com' --plugin list_assets

"""
import json
from praetorian_cli.plugins.utils import requires_package


@requires_package('numpy', '2.0.0')
def process(controller, cmd, cli_kwargs, output):

    from numpy.random import default_rng

    print(f'Using numpy here: {default_rng().random()}')

    # Verify the upstream CLI command is compatible with the script
    if cmd['product'] != 'chariot' or cmd['action'] != 'get' or cmd['type'] != 'asset':
        print("This script works with the 'get asset' command only.")
        return

    # Validate CLI output
    if not output:
        print("The CLI output is empty.")
        return

    asset_details = json.loads(output)

    if not asset_details['seed']:
        print("The asset is not a root asset; the seed field is False.")
        return

    # Extract the asset name
    asset = asset_details['name']

    # Search for asset name
    result = controller.my(dict(key=asset), pages=100)

    # Filter out attributes of the class 'seed'. Then, we compose asset keys from the attribute keys
    if 'attributes' in result:
        print(f"The following assets originate from {asset}:")
        for hit in result['attributes']:
            if hit['name'] == asset and hit['class'] == 'seed':
                fragments = hit['key'].split("#")
                print(f'#asset#{fragments[2]}#{fragments[3]}')
    else:
        print(f'No asset originate from {asset}')
