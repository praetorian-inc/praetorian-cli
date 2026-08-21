class Enrichment:

    def __init__(self, api):
        self.api = api

    def status(self):
        return self.api.get('enrichment')

    def enabled(self):
        return self.api.get('enrichment/enabled')

    # SDK-only method available for programmatic use; no corresponding CLI command exists.
    def set_enabled(self, plugins):
        return self.api.put('enrichment/enabled', plugins)

    def global_enabled(self):
        return self.api.get('enrichment/global/enabled')

    def set_global_enabled(self, enabled):
        return self.api.put('enrichment/global/enabled', {'enabled': enabled})

    def credits(self):
        return self.api.get('enrichment/credits')

    def plugin_status(self, plugin):
        return self.api.get(f'enrichment/{plugin}')

    def plugin_credits(self, plugin):
        return self.api.get(f'enrichment/{plugin}/credits')

    # SDK-only method available for programmatic use; no corresponding CLI command exists.
    def plugin_enabled(self, plugin):
        return self.api.get(f'enrichment/{plugin}/enabled')

    def set_plugin_enabled(self, plugin, enabled):
        return self.api.put(f'enrichment/{plugin}/enabled', {'enabled': enabled})

    def set_plugin_key(self, plugin, key):
        return self.api.put(f'enrichment/{plugin}/key', {'key': key})
