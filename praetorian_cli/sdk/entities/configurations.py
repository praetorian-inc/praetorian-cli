class Configurations:
    """
    Manage system configurations for Chariot capabilities and settings.

    This class provides methods to create, retrieve, update, and delete
    configurations that control capability behavior and system settings.
    All operations are restricted to Praetorian engineers only and require
    appropriate authentication.

    Configurations are accessed from sdk.configurations, where sdk is an
    instance of Chariot.

    Example:
        >>> chariot = Chariot()
        >>> chariot.configurations.add('nuclei', {'extra-tags': 'http,sql'})
        >>> config = chariot.configurations.get('#configuration#nuclei')
        >>> configs, offset = chariot.configurations.list('nuclei')
    """

    def __init__(self, api):
        self.api = api

    def _check_if_praetorian(self):
        if not self.api.is_praetorian_user():
            raise RuntimeError(
                "This option is limited to Praetorian engineers only. "
                "Please contact your Praetorian representative for assistance."
            )

    def add(self, name, value):
        """
        Add or update a configuration.

        This method creates a new configuration or updates an existing one
        with the same name. Configurations are key-value stores used to
        customize capability behavior and system settings. This functionality
        is restricted to Praetorian engineers only.

        :param name: The name of the configuration to add or update
        :type name: str
        :param value: Dictionary containing the configuration key-value pairs
        :type value: dict
        :return: The created or updated configuration entity
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.upsert('configuration', dict(name=name, value=value))

    def get(self, key):
        """
        Get a configuration by its exact key.

        Retrieves a specific configuration using its full key identifier.
        The key follows the pattern '#configuration#{name}' where name is
        the configuration name.

        :param key: The exact key of the configuration to retrieve
                   (e.g., '#configuration#nuclei')
        :type key: str
        :return: The configuration entity or None if not found
        :rtype: dict or None
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.search.by_exact_key(key)

    def delete(self, name):
        """
        Delete a configuration by name.

        Removes a configuration from the system. This action is irreversible.
        The configuration will no longer be available for capability execution
        or system operations.

        :param name: The name of the configuration to delete
        :type name: str
        :return: Result of the delete operation
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.delete('configuration', dict(name=name), {})

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List configurations with optional prefix filtering.

        Retrieves a list of configurations, optionally filtered by a prefix
        applied to the portion of the key after '#configuration#'. Supports
        pagination for large result sets.

        :param prefix_filter: Filter configurations by name prefix
                             (applied after '#configuration#')
        :type prefix_filter: str
        :param offset: The offset of the page you want to retrieve results from
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching configurations,
                 next page offset)
        :rtype: tuple
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.search.by_key_prefix(
            f'#configuration#{prefix_filter}', offset, pages
        )
