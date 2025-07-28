from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.model.query import Relationship, Node, Query, asset_of_key, RISK_NODE, ATTRIBUTE_NODE


class Assets:
    """ The methods in this class are to be assessed from sdk.assets, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, group, identifier, type=Kind.ASSET.value, status=Asset.ACTIVE.value, surface=''):
        """
        Add an asset to the account.

        :param group: The DNS or group identifier (e.g., domain name, repository URL)
        :type group: str
        :param identifier: The specific identifier (e.g., IP address, repository name)
        :type identifier: str
        :param type: Asset type from Kind enum (defaults to 'asset', can be 'addomain', 'repository')
        :type type: str
        :param status: Asset status from Asset enum ('A', 'F', 'D', 'P', 'FR')
        :type status: str
        :param surface: Attack surface classification (e.g., 'internal', 'external', 'web', 'api')
        :type surface: str
        :return: The asset that was added
        :rtype: dict
        """
        return self.api.upsert('asset', dict(group=group, identifier=identifier, status=status, surface=[surface], type=type))[0]

    def get(self, key, details=False):
        """
        Get details of an asset by key.

        :param key: Entity key in format #asset#{dns}#{name}
        :type key: str
        :param details: Whether to fetch additional details like attributes and risks
        :type details: bool
        :return: The asset matching the specified key
        :rtype: dict
        """
        asset = self.api.search.by_exact_key(key, details)
        if asset and details:
            asset['associated_risks'] = self.associated_risks(key)
        return asset

    def update(self, key, status=None, surface=None):
        """
        Update an asset.

        :param key: Entity key in format #asset#{dns}#{name}. If you supply a prefix that matches multiple assets, all of them will be updated
        :type key: str
        :param status: Asset status from Asset enum ('A', 'F', 'D', 'P', 'FR'), if None status is not updated
        :type status: str or None
        :param surface: Attack surface classification (e.g., 'internal', 'external'), if None surface is not updated
        :type surface: str or None
        :return: None
        :rtype: None
        """
        if status:
            self.api.upsert('asset', dict(key=key, status=status))
        if surface:
            self.api.attributes.add(key, 'surface', surface)

    def delete(self, key):
        """
        Delete an asset.

        :param key: Entity key in format #asset#{dns}#{name}. If you supply a prefix that matches multiple assets, all of them will be deleted
        :type key: str
        :return: The asset that was deleted
        :rtype: dict
        """
        return self.api.delete_by_key('asset', key)

    def list(self, prefix_filter='', asset_type='', offset=None, pages=100000) -> tuple:
        """
        List assets.

        :param prefix_filter: Supply this to perform prefix-filtering of the asset keys after the "#asset#" portion of the asset key. Asset keys read '#asset#{dns}#{name}'
        :type prefix_filter: str
        :param asset_type: The type of asset to filter by
        :type asset_type: str
        :param offset: The offset of the page you want to retrieve results. If this is not supplied, this function retrieves from the first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of assets, next page offset)
        :rtype: tuple
        """
        dns_prefix = ''
        if prefix_filter:
            dns_prefix = f'group:{prefix_filter}'
        if asset_type == '':
            asset_type = Kind.ASSET.value
        return self.api.search.by_term(dns_prefix, asset_type, offset, pages)

    def attributes(self, key):
        """
        Get attributes associated with an asset.

        :param key: Entity key in format #asset#{dns}#{name}
        :type key: str
        :return: List of attributes associated with the asset
        :rtype: list
        """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes

    def associated_risks(self, key):
        """
        Get risks associated with an asset.

        :param key: Entity key in format #asset#{dns}#{name}
        :type key: str
        :return: List of risks associated with the asset (both directly and indirectly via attributes)
        :rtype: list
        """
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
