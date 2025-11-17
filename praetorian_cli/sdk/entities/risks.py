from praetorian_cli.sdk.model.globals import Kind
from praetorian_cli.sdk.model.query import Relationship, Node, Query, risk_of_key, ASSET_NODE, PORT_NODE, Filter, WEBPAGE_NODE


class Risks:
    """ The methods in this class are to be assessed from sdk.risks, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, asset_key, name, status, comment=None, capability=''):
        """
        Add a risk to an existing asset.

        :param asset_key: The key of an existing asset to associate this risk with
        :type asset_key: str
        :param name: The name of this risk
        :type name: str
        :param status: Risk status from Risk enum (e.g., Risk.TRIAGE_HIGH.value, Risk.OPEN_CRITICAL.value). See globals.py for complete list of valid statuses
        :type status: str
        :param comment: Optional comment for the risk
        :type comment: str or None
        :param capability: Optional capability that discovered this risk
        :type capability: str
        :return: The created risk object
        :rtype: dict
        """
        return self.api.upsert('risk', dict(key=asset_key, name=name, status=status, comment=comment, source=capability))['risks'][0]

    def get(self, key, details=False):
        """
        Get details of a risk by its exact key.

        :param key: The exact key of a risk (format: #risk#{asset_dns}#{risk_name})
        :type key: str
        :param details: Whether to also retrieve more details about this risk. This will make additional API calls to get the risk attributes and affected assets
        :type details: bool
        :return: The matching risk object or None if not found
        :rtype: dict or None
        """
        risk = self.api.search.by_exact_key(key, details)
        if risk and details:
            risk['affected_assets'] = self.affected_assets(key)
        return risk

    def update(self, key, status=None, comment=None):
        """
        Update a risk's status and/or comment.

        :param key: The key of the risk. If you supply a prefix that matches multiple risks, all of them will be updated
        :type key: str
        :param status: New risk status from Risk enum (e.g., Risk.OPEN_HIGH.value, Risk.REMEDIATED_CRITICAL.value). See globals.py for complete list of valid statuses
        :type status: str or None
        :param comment: Comment for the risk update
        :type comment: str or None
        :return: API response containing update results
        :rtype: dict
        """
        params = dict(key=key)
        if status:
            params = params | dict(status=status)
        if comment:
            params = params | dict(comment=comment)

        return self.api.upsert('risk', params)

    def delete(self, key, status, comment=None):
        """
        Delete a risk by setting it to a deleted status.

        :param key: The key of the risk. If you supply a prefix that matches multiple risks, all of them will be deleted
        :type key: str
        :param status: Deletion status from Risk enum (e.g., Risk.DELETED_DUPLICATE_CRITICAL.value, Risk.DELETED_FALSE_POSITIVE_HIGH.value)
        :type status: str
        :param comment: Optional comment for this deletion operation
        :type comment: str or None
        :return: API response containing deletion results
        :rtype: dict
        """
        body = dict(status=status)

        if comment:
            body = body | dict(comment=comment)

        return self.api.delete_by_key('risk', key, body)

    def list(self, contains_filter='', offset=None, pages=100000) -> tuple:
        """
        List risks with optional filtering and pagination.

        :param contains_filter: Filter to apply to the risk key. Ensure the risk's key contains the filter.
        :type contains_filter: str
        :param offset: The offset of the page you want to retrieve results. If not supplied, retrieves from the first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching risks, next page offset)
        :rtype: tuple
        """
        filters = []
        if contains_filter:
            contains_filter_filter = Filter(field=Filter.Field.KEY, operator=Filter.Operator.CONTAINS, value=contains_filter)
            filters.append(contains_filter_filter)

        query = Query(
            Node(
                labels=[Node.Label.RISK],
                filters=filters
            )
        )

        if offset:
            query.page = int(offset)

        return self.api.search.by_query(query, pages)

    def attributes(self, key):
        """
        List attributes associated with a risk.

        :param key: The key of the risk to get attributes for
        :type key: str
        :return: List of attribute objects associated with the risk
        :rtype: list
        """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes

    def affected_assets(self, key):
        """
        Get all assets affected by a risk.

        This method finds assets that are directly linked to the risk via HAS_VULNERABILITY
        relationships, as well as assets indirectly linked via ports that have the risk.

        :param key: The key of the risk to get affected assets for
        :type key: str
        :return: List of asset objects affected by the risk (both directly and indirectly linked)
        :rtype: list
        """
        # assets directly linked to the risk
        to_this = Relationship(Relationship.Label.HAS_VULNERABILITY, target=risk_of_key(key))
        query = Query(Node(ASSET_NODE, relationships=[to_this]))
        assets, _ = self.api.search.by_query(query)

        # assets indirectly linked to the risk via a port
        ports = Node(PORT_NODE, relationships=[to_this])
        to_ports = Relationship(Relationship.Label.HAS_PORT, target=ports)
        query = Query(Node(ASSET_NODE, relationships=[to_ports]))
        indirect_assets, _ = self.api.search.by_query(query)

        # webpages linked to the risk
        webpages = Node(WEBPAGE_NODE, relationships=[to_this])
        to_webpages = Relationship(Relationship.Label.HAS_WEBPAGE, target=webpages)
        query = Query(Node(ASSET_NODE, relationships=[to_webpages]))
        web_assets, _ = self.api.search.by_query(query)

        assets.extend(indirect_assets)
        assets.extend(web_assets)
        return assets
