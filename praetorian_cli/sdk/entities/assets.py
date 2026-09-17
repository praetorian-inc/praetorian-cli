from praetorian_cli.sdk.model.globals import Asset, Kind
from praetorian_cli.sdk.model.query import Relationship, Node, Query, Filter, KIND_TO_LABEL, asset_of_key, RISK_NODE, ATTRIBUTE_NODE


HUNT_SCOPE_CLASSES = {
    'hannibal': ['domain', 'tld', 'ipv4', 'ipv6', 'cidr'],
    'hannibal-cloud': ['amazon', 'azure', 'gcp'],
}
HUNT_WEB_AGENTS = {'hannibal-webapp', 'hannibal-llm'}


class Assets:
    """ The methods in this class are to be assessed from sdk.assets, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, group, identifier, type=Kind.ASSET.value, status=Asset.ACTIVE.value, surface='', resource_type=''):
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
        :param resource_type: Cloud resource type (e.g., 'compute.googleapis.com/Instance', 'AWS::EC2::Instance')
        :type resource_type: str
        :return: The asset that was added
        :rtype: dict
        """
        payload = dict(group=group, identifier=identifier, status=status, attackSurface=[surface], type=type)
        if resource_type:
            payload['resourceType'] = resource_type
        return self.api.upsert('asset', payload)[0]

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

    def update(self, key, status=None, surface=None, secret=None):
        """
        Update an asset.

        :param key: Entity key in format #asset#{dns}#{name}. If you supply a prefix that matches multiple assets, all of them will be updated
        :type key: str
        :param status: Asset status from Asset enum ('A', 'F', 'D', 'P', 'FR'), if None status is not updated
        :type status: str or None
        :param surface: Attack surface classification (e.g., 'internal', 'external'), if None surface is not updated
        :type surface: str or None
        :param secret: For WebApplication assets, the credential ID to set as the default credential.
            If None, the secret is not updated.
        :type secret: str or None
        :return: None
        :rtype: None
        """
        params = dict(key=key)
        if status:
            params = params | dict(status=status)
        if surface:
            params = params | dict(attackSurface=[surface])
        if secret is not None:
            params = params | dict(secret=secret)

        return self.api.upsert('asset', params)

    def delete(self, key):
        """
        Delete an asset.

        :param key: Entity key in format #asset#{dns}#{name}. If you supply a prefix that matches multiple assets, all of them will be deleted
        :type key: str
        :return: The asset that was deleted
        :rtype: dict
        """
        return self.api.delete_by_key('asset', key)

    def list(self, key_prefix='', asset_type='', pages=100000) -> tuple:
        """
        List assets.

        :param key_prefix: Supply this to perform prefix-filtering of the asset key. E.g., '#asset#example.com' or '#addomain#sevenkingdoms'
        :type key_prefix: str
        :param asset_type: The type of asset to filter by
        :type asset_type: str
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of assets, next page offset)
        :rtype: tuple
        """

        if asset_type in KIND_TO_LABEL:
            asset_type = KIND_TO_LABEL[asset_type]
        elif not asset_type:
            asset_type = Node.Label.ASSET
        else:
            raise ValueError(f'Invalid asset type: {asset_type}')

        node = Node(
            labels=[asset_type],
            filters=[]
        )

        key_filter = Filter(
            field=Filter.Field.KEY,
            operator=Filter.Operator.STARTS_WITH,
            value=key_prefix
        )

        if key_prefix:
            node.filters.append(key_filter)

        query = Query(node=node)

        return self.api.search.by_query(query, pages)

    def list_hunt_scope(
        self,
        agent='hannibal',
        internal=False,
        search='',
        page=0,
        pages=1,
    ):
        """List active targets selectable by the Hunt launch UI."""
        if internal and agent != 'hannibal':
            raise ValueError('Internal Hunts require the Hannibal agent')
        if agent not in HUNT_SCOPE_CLASSES and agent not in HUNT_WEB_AGENTS:
            raise ValueError(f'Unsupported Hunt agent: {agent}')

        is_web_application = agent in HUNT_WEB_AGENTS
        filters = [
            Filter(
                Filter.Field.STATUS,
                Filter.Operator.STARTS_WITH,
                Asset.ACTIVE.value,
            )
        ]
        if not is_web_application:
            classes = ['ipv4', 'cidr'] if internal else HUNT_SCOPE_CLASSES[agent]
            filters.append(Filter(
                Filter.Field.CLASS,
                Filter.Operator.IN,
                [classes],
            ))
        if internal:
            filters.append(Filter(
                Filter.Field.IS_INTERNAL,
                Filter.Operator.EQUAL,
                True,
            ))
        if agent == 'hannibal-llm':
            filters.append(Filter(
                Filter.Field.IS_LLM,
                Filter.Operator.EQUAL,
                True,
            ))

        label = (
            Node.Label.WEBAPPLICATION
            if is_web_application
            else Node.Label.ASSET
        )
        node = Node(labels=[label], filters=filters)
        query_filters = None
        if search and not is_web_application:
            node.search = search
        elif search:
            search_conditions = [
                Filter(field, Filter.Operator.CONTAINS, search).to_dict()
                for field in (
                    Filter.Field.KEY,
                    Filter.Field.NAME,
                    Filter.Field.PRIMARY_URL,
                    Filter.Field.IDENTIFIER,
                    Filter.Field.DOMAIN,
                )
            ]
            query_filters = [
                Filter('', Filter.Operator.OR, search_conditions)
            ]
        return self.api.search.by_query(
            Query(
                node=node,
                page=page,
                limit=200,
                filters=query_filters,
            ),
            pages,
        )

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

    def bulk_add(self, items):
        """Add multiple assets in a single bulk operation (async).

        Args:
            items: List of dicts with keys: group, identifier,
                   and optionally: type, status, surface, resource_type

        Returns:
            Job dict for tracking progress. Use sdk.jobs.bulk_results(job)
            to get per-item results after completion.
        """
        payload_items = []
        for item in items:
            p = dict(
                group=item['group'],
                identifier=item['identifier'],
                status=item.get('status', Asset.ACTIVE.value),
                attackSurface=[item.get('surface', '')],
                type=item.get('type', Kind.ASSET.value),
            )
            if item.get('resource_type'):
                p['resourceType'] = item['resource_type']
            payload_items.append(p)
        return self.api.post('bulk/asset', dict(action='upsert', items=payload_items))

    def associated_risks(self, key):
        """
        Get risks associated with an asset.

        :param key: Entity key in format #asset#{dns}#{name}
        :type key: str
        :return: List of risks associated with the asset (both directly and indirectly via attributes)
        :rtype: list
        """
        # risks directly linked to the asset
        risks_from_this = Relationship([Relationship.Label.HAS_VULNERABILITY], source=asset_of_key(key))
        query = Query(Node(RISK_NODE, relationships=[risks_from_this]))
        risks, _ = self.api.search.by_query(query)

        # risks indirectly linked to this asset via asset attributes
        attributes_from_this = Relationship([Relationship.Label.HAS_ATTRIBUTE], source=asset_of_key(key))
        attributes = Node(ATTRIBUTE_NODE, relationships=[attributes_from_this])
        risks_from_attributes = Relationship([Relationship.Label.HAS_VULNERABILITY], source=attributes)
        query = Query(Node(RISK_NODE, relationships=[risks_from_attributes]))
        indirect_risks, _ = self.api.search.by_query(query)

        risks.extend(indirect_risks)
        return risks
