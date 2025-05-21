from praetorian_cli.handlers.cli_decorators import praetorian_only


class Configurations:
    """ The methods in this class are to be assessed from sdk.configurations, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def _check_if_praetorian(self):
        if not self.api.is_praetorian_user():
            raise RuntimeError("This option is limited to Praetorian engineers only. Please contact your Praetorian representative for assistance.")

    def add(self, name, value):
        """ Add a new configuration """
        self._check_if_praetorian()
        if isinstance(value, str):
            try:
                import json
                value = json.loads(value)
            except:
                pass
        return self.api.upsert('configuration', dict(name=name, value=value))
        
    def update(self, name, entries):
        """ Update a configuration with new key-value pairs """
        self._check_if_praetorian()
        from praetorian_cli.sdk.model.utils import configuration_key
        config_key = configuration_key(name)
        existing_config = self.get(config_key)
        if not existing_config:
            raise ValueError(f"Configuration '{name}' not found")
        
        current_value = existing_config.get('value', {})
        if isinstance(current_value, str):
            try:
                import json
                current_value = json.loads(current_value)
            except:
                current_value = {}
        
        for key, value in entries.items():
            if value == "":
                if key in current_value:
                    del current_value[key]
            else:
                current_value[key] = value
        
        return self.api.upsert('configuration', dict(name=name, value=current_value))

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
