class Scanners:

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """ Get scanner details by exact key """
        return self.api.search.by_exact_key(key)

    def list(self, filter='', offset='', page_size=100):
        """ List scanners with optional filtering """
        search_term = f"#scanner#{filter}"
        return self.api.search.by_term(search_term, None, offset, page_size)