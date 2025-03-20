from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.entities.search import Relationship, Node, Query, asset_of_key, RISK_NODE, ATTRIBUTE_NODE


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
        return self.api.delete_by_key('asset', key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
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
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes

    def associated_risks(self, key):
        # risks directly linked to the asset
        risks_from_this = Relationship(Relationship.Label.HAS_VULNERABILITY, source=asset_of_key(key))
        query = Query(Node(RISK_NODE, relationships=[risks_from_this]))
        risks, _ = self.api.search.by_query(query)

        # risks indirectly linked to this asset via asset attributes
        attributes_from_this = Relationship(Relationship.Label.HAS_ATTRIBUTE, source=asset_of_key(key))
        attributes = Node(ATTRIBUTE_NODE, relationships=[attributes_from_this])
        risks_from_attributes = Relationship(Relationship.Label.HAS_VULNERABILITY, source=attributes)
        query = Query(Node(RISK_NODE, relationships=[risks_from_attributes]))
        indirect_risks, _ = self.api.search.by_query(query)

        risks.extend(indirect_risks)
        return risks
