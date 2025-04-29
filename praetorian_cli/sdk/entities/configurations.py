class Configurations:
    """ The methods in this class are to be assessed from sdk.configurations, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, name, value):
        """ Add a new configuration """
        return self.api.upsert('configuration', dict(name=name, value=value))

    def get(self, key):
        """ Get details of a configuration """
        return self.api.search.by_exact_key(key)

    def delete(self, key):
        """ Delete a configuration """
        return self.api.delete_by_key('configuration', key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List configuration, optionally prefix-filtered by the portion of the key after
            '#configuration#' """
        return self.api.search.by_key_prefix(f'#configuration#{prefix_filter}', offset, pages) 