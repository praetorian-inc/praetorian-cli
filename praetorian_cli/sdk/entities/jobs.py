class Jobs:
    """ The methods in this class are to be assessed from sdk.jobs, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, target_key):
        """ Add a job for an asset or an attribute """
        return self.api.force_add('job', dict(key=target_key))

    def get(self, key):
        """ Get details of a job """
        return self.api.search.by_exact_key(key)

    def list(self, prefix_filter='', offset=None, pages=1000):
        """ List jobs, optionally prefix-filtered by the portion of the key after
            '#job#' """
        return self.api.search.by_key_prefix(f'#job#{prefix_filter}', offset, pages)
