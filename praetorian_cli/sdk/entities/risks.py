from praetorian_cli.sdk.model.globals import Kind
from praetorian_cli.sdk.entities.search import Relationship, Node, Query, risk_of_key, ASSET_NODE, ATTRIBUTE_NODE


class Risks:
    """ The methods in this class are to be assessed from sdk.risks, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, asset_key, name, status, comment=None):
        """ Add a risk

        Arguments:
        asset_key:
            The key of an existing asset to associate this risk with
        name: str
            The name of this risk
        status: str
            See globals.py for list of valid statuses
        comment: str
            Optional comment
        """
        return self.api.upsert('risk', dict(key=asset_key, name=name, status=status, comment=comment))['risks'][0]

    def get(self, key, details=False):
        """ Get details of a risk

        Arguments:
        key: str
            The exact key of an risk.
        details: bool
            Specify whether to also retrieve more details about this risk. This will make more API calls
            to get the risk attributes and the affected assets.
        """
        risk = self.api.search.by_exact_key(key, details)
        if risk and details:
            risk['affected_assets'] = self.affected_assets(key)
        return risk

    def update(self, key, status=None, comment=None):
        """ Update a risk

        Arguments:
        key: str
            The key of the risk. If you supply a prefix that matches multiple risks,
            all of them will be updated.
        status: str
            See globals.py for list of valid statuses
        comment: str
            Comment for the risk
        """
        params = dict(key=key)
        if status:
            params = params | dict(status=status)
        if comment:
            params = params | dict(comment=comment)

        return self.api.upsert('risk', params)

    def delete(self, key, status, comment=None):
        """ Delete a risk.

        Arguments:
        key: str
            The key of the risk. If you supply a prefix that matches multiple risks,
            all of them will be deleted.
        comment: str
            Optionally, provide a comment for this operation.
        """
        body = dict(status=status)

        if comment:
            body = body | dict(comment=comment)

        return self.api.delete_by_key('risk', key, body)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List risks

        Arguments:
        prefix_filter: str
            Supply this to perform prefix-filtering of the risk keys after the "#risk#"
            portion of the key. Risk keys read '#risk#{asset_dns}#{risk_name}'

        offset: str
            The offset of the page you want to retrieve results. If this is not supplied,
            this function retrieves from the first page.
        pages: int
            The number of pages of results to retrieve.
        """
        return self.api.search.by_key_prefix(f'#risk#{prefix_filter}', offset, pages)

    def attributes(self, key):
        """ list associated attributes """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes

    def affected_assets(self, key):
        # assets directly linked to the risk
        to_this = Relationship(Relationship.Label.HAS_VULNERABILITY, target=risk_of_key(key))
        query = Query(Node(ASSET_NODE, relationships=[to_this]))
        assets, _ = self.api.search.by_query(query)

        # assets indirectly linked to the risk via an attribute
        attributes = Node(ATTRIBUTE_NODE, relationships=[to_this])
        to_attributes = Relationship(Relationship.Label.HAS_ATTRIBUTE, target=attributes)
        query = Query(Node(ASSET_NODE, relationships=[to_attributes]))
        indirect_assets, _ = self.api.search.by_query(query)

        assets.extend(indirect_assets)
        return assets
