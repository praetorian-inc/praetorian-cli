from praetorian_cli.handlers.utils import error
from praetorian_cli.sdk.model.globals import Seed


class Seeds:
    """ The methods in this class are to be assessed from sdk.seeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, dns, status=Seed.PENDING.value):
        """ Add a seed """
        return self.api.upsert('seed', dict(dns=dns, status=status))

    def get(self, key, details=False):
        """ Get details of a seed """
        seed = self.api.search.by_exact_key(key, details)
        return seed

    def update(self, key, status):
        """ Update a seed; only status field makes sense to be updated. """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # the seed PUT endpoint is different from other PUT endpoints. This one has to
            # take the DNS of the original seed, instead of the key of the seed record.
            # TODO, 2024-12-23, peter: check with Noah as to why. Ideally, we should
            # standardize to how other endpoints do it
            return self.api.upsert('seed', dict(dns=seed['dns'], status=status))
        else:
            error(f'Seed {key} is not found.')

    def delete(self, key):
        """ Delete a seed """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # TODO, 2024-12-23, peter: check with Noah why this is different from
            # deleting assets and risks
            return self.api.upsert('seed', dict(dns=seed['dns'], status=Seed.DELETED.value))
        else:
            error(f'Seed {key} is not found.')

    def list(self, type='', prefix_filter='', offset=None, pages=10000):
        """ List seeds """
        prefix_term = '#seed#'
        if type:
            prefix_term = f'{prefix_term}{type}#'
        if prefix_filter:
            prefix_term = f'{prefix_term}{prefix_filter}'

        return self.api.search.by_key_prefix(prefix_term, offset, pages)

    def attributes(self, key):
        """ list associated attributes """
        attributes, _ = self.api.search.by_source(key)
        return attributes
