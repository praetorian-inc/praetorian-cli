from os.path import basename


class Integrations:
    """ The methods in this class are to be assessed from sdk.integrations, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """
        Get details of an integration by its exact key.

        :param key: The exact key of the integration to retrieve (format: #account#{username}#{integration_type}#{integration_id})
        :type key: str
        :return: The matching integration entity or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key)

    def list(self, name_filter='', offset=None, pages=100000) -> tuple:
        """
        List integrations, optionally filtered by the name of the integrations.

        Retrieves integration connections such as cloud providers (amazon, gcp, azure), 
        source code managers (github, gitlab, bitbucket), vulnerability scanners (crowdstrike, 
        nessus, qualys), notification systems (slack, email, jira), and other security tools.
        Filters out user accounts and settings entries.

        :param name_filter: Filter results by integration name (e.g., 'github', 'amazon', 'gcp', 'azure', 'crowdstrike', 'slack', 'jira')
        :type name_filter: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching integration entities, next page offset)
        :rtype: tuple
        """
        results, next_offset = self.api.search.by_key_prefix('#account#', offset, pages)

        # filter out the user accounts and settings
        results = [i for i in results if
                   '@' not in i['member'] and i['member'] != 'settings' and i['member'] != 'settings-display-name']

        # filter for integration names, such as 'github', 'amazon'
        if name_filter:
            results = [i for i in results if name_filter == i['name'] or name_filter == i['member']]

        return results, next_offset

    def add_import_integration(self, name, local_filepath):
        """
        Add an import integration for vulnerability scanner data.

        Creates an integration that imports vulnerability data from external scanners
        by uploading the file to Chariot's file system and linking it as an account integration.
        Commonly used for importing data from vulnerability scanners like InsightVM, Qualys, and Nessus.

        :param name: The name of the import integration (e.g., 'insightvm-import', 'qualys-import', 'nessus-import')
        :type name: str
        :param local_filepath: The local file path to the vulnerability scanner export file
        :type local_filepath: str
        :return: None
        :rtype: None
        """
        chariot_filename = f'imports/{name}/{basename(local_filepath)}'
        self.api.files.add(local_filepath, chariot_filename)
        self.api.link_account(name, chariot_filename)
