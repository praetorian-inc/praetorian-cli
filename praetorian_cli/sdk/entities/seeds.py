from praetorian_cli.handlers.utils import error
from praetorian_cli.sdk.model.globals import Seed, Kind

from praetorian_cli.sdk.model.query import Query, Node, Filter


class Seeds:
    """ The methods in this class are to be assessed from sdk.seeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, value, seed_type, status=Seed.PENDING.value):
        """ Add a seed """
        if not seed_type.endswith('seed'):
            seed_type = seed_type + 'seed'
        return self.api.upsert('seed', dict(value=value, type=seed_type, status=status))

    def get(self, key):
        """ Get details of a seed """
        return self.api.search.by_exact_key(key, False)

    def update(self, key, status):
        """ Update a seed; only status field makes sense to be updated. """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # the seed PUT endpoint is different from other PUT endpoints. This one has to
            # take the DNS of the original seed, instead of the key of the seed record.
            # TODO, 2024-12-23, peter: check with Noah as to why. Ideally, we should
            # standardize to how other endpoints do it
            return self.api.upsert('seed', dict(key=key, value=seed['value'], status=status))
        else:
            error(f'Seed {key} is not found.')

    def delete(self, key):
        """ Delete a seed """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # TODO, 2024-12-23, peter: check with Noah why this is different from
            # deleting assets and risks
            return self.api.upsert('seed', dict(key=key, value=seed['value'], status=Seed.DELETED.value))
        else:
            error(f'Seed {key} is not found.')

    def list(self, seed_type='seed', prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List seeds """
        filters = []
        if prefix_filter:
            filters=[Filter(field=Filter.Field.VALUE, operator=Filter.Operator.CONTAINS, value=prefix_filter)]
        
        if not seed_type.endswith('seed'):
            seed_type = seed_type + 'seed'
        try:
            seed_kind = Kind(seed_type)
        except ValueError:
            seed_kind = Kind.SEED

        node = Node(labels=[seed_kind], filters=filters)
        query = Query(node=node, offset=offset)
        return self.api.search.by_query(query, pages)

    def attributes(self, key):
        """ list associated attributes """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes
