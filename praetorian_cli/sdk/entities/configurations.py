from praetorian_cli.handlers.cli_decorators import praetorian_only


class Configurations:
    """ The methods in this class are to be assessed from sdk.configurations, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def _check_if_praetorian(self):
        if not self.api.is_praetorian_user():
            raise RuntimeError("This option is limited to Praetorian engineers only. Please contact your Praetorian representative for assistance.")

    def add(self, name, value: dict):
        """ Add a new configuration """
        self._check_if_praetorian()
        return self.api.upsert('configuration', dict(name=name, value=value))



    def get(self, key):
        """ Get details of a configuration """
        self._check_if_praetorian()
        return self.api.search.by_exact_key(key)

    def delete(self, name):
        """ Delete a configuration """
        self._check_if_praetorian()
        return self.api.delete('configuration', dict(name=name), {})

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List configuration, optionally prefix-filtered by the portion of the key after
            '#configuration#' """
        self._check_if_praetorian()
        return self.api.search.by_key_prefix(f'#configuration#{prefix_filter}', offset, pages)
