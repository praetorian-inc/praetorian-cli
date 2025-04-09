from praetorian_cli.handlers.utils import error


class Preseeds:
    """ The methods in this class are to be assessed from sdk.preseeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, type, title, value, status):
        """ Add a pre-seed """
        return self.api.force_add('preseed', dict(type=type, title=title, value=value, status=status))

    def get(self, key, details=False):
        """ Get details of a pre-seed """
        return self.api.search.by_exact_key(key, details)

    def update(self, key, status):
        """ Update a pre-seeds; only status field makes sense to be updated. """
        preseed = self.api.search.by_exact_key(key)
        if preseed:
            return self.api.update('preseed', dict(key=key, status=status))
        else:
            error(f'Pre-seed {key} is not found.')

    def delete(self, key):
        """ Delete a pre-seeds """
        return self.api.delete_by_key('preseed', key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List pre-seeds """
        return self.api.search.by_key_prefix(f'#preseed#{prefix_filter}', offset, pages)
