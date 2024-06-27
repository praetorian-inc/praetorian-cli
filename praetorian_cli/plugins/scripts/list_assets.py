"""
This script retrieves the assets discovered by a given seed. It retrieves
the seed from the CLI. In turn, it execute a search using the my() function
of the Chariot SDK to find all entities related to the seed. Finally, it
filters for the attributes entities, which store the information of
the assets under the seed.

Example usage:

  praetorian chariot get seed '#seed#praetorian.com' --plugin list_assets

"""
import json


def process(controller, cmd, cli_kwargs, output):
    # Verify the upstream CLI command is compatible with the script
    if cmd['product'] != 'chariot' or cmd['action'] != 'get' or cmd['type'] != 'seed':
        print("This script works with the 'get seed' command only.")
        return

    # Validate CLI output
    if not output:
        print("The CLI output is empty.")
        return

    seed_details = json.loads(output)

    # Extract the seed name
    seed = seed_details['name']

    print(f"Seed '{seed}' has the following assets:")

    # Search for seed name
    result = controller.my(dict(key=seed), pages=100)

    # Filter out attributes of the class 'seed'. Then, we compose asset keys from the attribute keys
    for hit in result['attributes']:
        if hit['name'] == seed and hit['class'] == 'seed':
            fragments = hit['key'].split("#")
            print(f'#asset#{fragments[2]}#{fragments[3]}')
