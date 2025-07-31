class Settings:
    """ The methods in this class are to be assessed from sdk.settings, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, name, value):
        """
        Add a new setting to Chariot.

        Creates or updates a setting with the specified name and value. Settings are 
        key-value pairs used to configure various aspects of the Chariot platform.

        :param name: The name of the setting to create or update
        :type name: str
        :param value: The value to assign to the setting (can be string or JSON)
        :type value: str
        :return: Dictionary containing the created setting with 'name' and 'value' keys
        :rtype: dict
        """
        return self.api.upsert('setting', dict(name=name, value=value))

    def get(self, key):
        """
        Get details of a specific setting by its key.

        Retrieves a setting using its full key in the format '#setting#{name}'.
        Returns None if the setting does not exist.

        :param key: The full key of the setting (e.g., '#setting#rate-limit')
        :type key: str
        :return: Dictionary containing setting details with 'name' and 'value' keys, or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key)

    def delete(self, name):
        """
        Delete a setting by its name.

        Removes the specified setting from Chariot. The setting name should be 
        provided without the '#setting#' prefix.

        :param name: The name of the setting to delete (without key prefix)
        :type name: str
        :return: Dictionary containing the deleted setting information
        :rtype: dict
        """
        return self.api.delete('setting', dict(name=name), {})

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List settings with optional prefix filtering.

        Retrieves a list of settings, optionally filtered by a prefix applied to the 
        portion of the key after '#setting#'. Supports pagination for large result sets.

        :param prefix_filter: Filter settings by name prefix (applied after '#setting#')
        :type prefix_filter: str
        :param offset: The offset of the page you want to retrieve results from
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching settings, next page offset)
        :rtype: tuple
        """
        return self.api.search.by_key_prefix(f'#setting#{prefix_filter}', offset, pages)
