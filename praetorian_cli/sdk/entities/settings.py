class Settings:
    """ The methods in this class are to be assessed from sdk.settings, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, name, value):
        """ Add a new setting """
        return self.api.upsert('setting', dict(name=name, value=value))

    def get(self, key):
        """ Get details of a setting """
        return self.api.search.by_exact_key(key)

    def delete(self, name):
        """ Delete a setting """
        return self.api.delete('setting', dict(name=name), {})

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List setting, optionally prefix-filtered by the portion of the key after
            '#setting#' """
        return self.api.search.by_key_prefix(f'#setting#{prefix_filter}', offset, pages)
