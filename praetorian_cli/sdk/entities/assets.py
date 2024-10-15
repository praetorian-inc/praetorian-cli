from praetorian_cli.sdk.model.globals import Asset


class Assets:
    """ The methods in this class are to be assessed from sdk.assets, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, dns, name, status=Asset.ACTIVE.value):
        """ Add an asset

        Arguments:
        dns: str
            The DNS name of the asset
        name: str
            The name of the asset
        status: str
            See globals.py for list of valid statuses
        """
        return self.api.upsert('asset', dict(dns=dns, name=name, status=status))[0]

    def get(self, key, details=False):
        """ Get details of an asset

        Arguments:
        key: str
            The exact key of an asset.
        details: bool
            Specify whether to also retrieve more details with this asset. This will
            make more API calls for the asset attributes and the associated risks.
        """
        asset = self.api.search.by_exact_key(key, details)
        if asset and details:
            asset['associated_risks'] = self.associated_risks(key)
        return asset

    def update(self, key, status):
        """ Update an asset; only status field makes sense to be updated.

        Arguments:
        key: str
            The key of an asset. If you supply a prefix that matches multiple assets,
            all of them will be updated.
        status: str
            See globals.py for list of valid statuses
        """
        return self.api.upsert('asset', dict(key=key, status=status))

    def delete(self, key):
        """ Delete an asset

        Arguments:
        key: str
            The key of an asset. If you supply a prefix that matches multiple assets,
            all of them will be deleted.
        """
        return self.api.delete('asset', key)

    def list(self, prefix_filter='', offset=None, pages=1000):
        """ List assets

        Arguments:
        prefix_filter: str
            Supply this to perform prefix-filtering of the asset keys after the "#asset#"
            portion of the asset key. Asset keys read '#asset#{dns}#{name}'
        offset: str
            The offset of the page you want to retrieve results. If this is not supplied,
            this function retrieves from the first page.
        pages: int
            The number of pages of results to retrieve.
        """
        return self.api.search.by_key_prefix(f'#asset#{prefix_filter}', offset, pages)

    def attributes(self, key):
        """ list associated attributes """
        attributes, _ = self.api.search.by_source(key)
        return attributes

    def associated_risks(self, key):
        asset = self.get(key)
        if asset:
            risks, _ = self.api.risks.list(asset['dns'])
            return risks
        else:
            return []
