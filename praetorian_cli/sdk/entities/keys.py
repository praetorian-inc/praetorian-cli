class Keys:
    """ The methods in this class are to be assessed from sdk.keys, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, name, expires):
        """ Add a new API key """
        return self.api.force_add('key', dict(name=name, expires=expires))

    def get(self, key):
        """ Get details of an API key """
        return self.api.search.by_exact_key(key)

    def delete(self, key):
        """ Delete an API key """
        return self.api.delete('key', dict(key=key), {})

    def list(self, offset=None, pages=100000) -> tuple:
        """ List API keys """
        return self.api.search.by_key_prefix('#key#', offset, pages)
