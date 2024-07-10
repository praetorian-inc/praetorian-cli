from praetorian_cli.sdk.chariot import Chariot


class Asset(Chariot):
    def __init__(self, keychain, key, asset_data=None):
        super().__init__(keychain)
        self.key = key
        self.data = asset_data or {
            "name": "",
            "type": "",
            "value": 0,
            "created": "",
            "source": ""
        }
        if asset_data:
            print(f"Asset {key} initialized with data: {asset_data}")
        else:
            print(f"Asset {key} initialized with no data.")

    def add_asset(self, asset_data):
        """
        Adds data to the asset.

        :param asset_data: Dictionary containing asset data
        """
        self.data.update(asset_data)
        print(f"Asset {self.key} added with data: {self.data}")

    def update_asset(self, asset_data):
        """
        Updates the asset data.

        :param asset_data: Dictionary containing updated asset data
        """
        self.data.update(asset_data)
        print(f"Asset {self.key} updated with data: {self.data}")

    def delete_asset(self):
        """
        Deletes the asset data.
        """
        self.data = None
        print(f"Asset {self.key} deleted.")

    def get_asset(self):
        """
        Retrieves the asset data.

        :return: Dictionary containing asset data
        """
        return self.data

    def __getattr__(self, item):
        """
        Custom attribute access to get data properties directly.
        """
        if item in self.data:
            return self.data[item]
        raise AttributeError(f"'Asset' object has no attribute '{item}'")
