"""
This script retrieves the assets originating from a given asset. It retrieves
the asset from the CLI. In turn, it execute a search using the my() function
of the Chariot SDK to find all entities related to the asset. It is done by
querying for attributes where the name is "source" and "value" is the
name of the originating asset. Finally, the script filters the attributes
that belong to assets (as opposed to risks).

Example usage:

  praetorian chariot get asset '#asset#praetorian.com#praetorian.com' --plugin list_assets

"""
import json


def process(controller, cmd, cli_kwargs, output):
    # Verify the upstream CLI command is compatible with the script
    if cmd['product'] != 'chariot' or cmd['action'] != 'get' or cmd['type'] != 'asset':
        print("This script works with the 'get asset' command only.")
        return

    # Validate CLI output
    if not output:
        print("The CLI output is empty.")
        return

    asset_details = json.loads(output)

    # Extract the asset name
    asset = asset_details['name']

    # Search for asset name
    result = controller.my(dict(key=f'#attribute#source#{asset}'), pages=100)

    # Filter out attributes of the class 'seed'. Then, we compose asset keys from the attribute keys
    if 'attributes' in result:
        print(f"The following assets originate from {asset}:")
        for hit in result['attributes']:
            if hit['source'].startswith('#asset'):
                print(hit['source'])
    else:
        print(f'No assets originate from {asset}.')
