class Attributes:
    """ The methods in this class are to be assessed from sdk.attributes, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, source_key, name, value):
        """ Add an attribute for an existing asset or risk """
        return self.api.upsert('attribute', dict(key=source_key, name=name, value=value))['attributes'][0]

    def get(self, key):
        """ Get details of an attribute """
        return self.api.search.by_exact_key(key)

    def update(self, key, status):
        """ Update an attribute """
        return self.api.upsert('attribute', dict(key=key, status=status))

    def delete(self, key):
        """ Delete an attribute """
        return self.api.delete('attribute', key)

    def list(self, prefix_filter='', source_key=None, offset=None, pages=10000):
        """ List attribute, optionally prefix-filtered by the portion of the key after
            '#attribute#' """
        if source_key:
            return self.api.search.by_source(source_key, offset, pages)
        else:
            return self.api.search.by_key_prefix(f'#attribute#{prefix_filter}', offset, pages)
