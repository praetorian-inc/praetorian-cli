from os.path import basename


class Integrations:
    """ The methods in this class are to be assessed from sdk.integrations, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """ Get details of an integration """
        return self.api.search.by_exact_key(key)

    def list(self, name_filter='', offset=None, pages=10000):
        """ List integrations, optionally filtered by the name of the integrations,
            such as github, amazon, gcp, etc. """
        results, next_offset = self.api.search.by_key_prefix('#account#', offset, pages)

        # filter out the user accounts and settings
        results = [i for i in results if '@' not in i['member'] and i['member'] != 'settings']

        # filter for integration names, such as 'github', 'amazon'
        if name_filter:
            results = [i for i in results if name_filter == i['name'] or name_filter == i['member']]

        return results, next_offset

    def add_import_integration(self, name, local_filepath):
        chariot_filename = f'imports/{name}/{basename(local_filepath)}'
        self.api.files.add(local_filepath, chariot_filename)
        self.api.link_account(name, chariot_filename)
