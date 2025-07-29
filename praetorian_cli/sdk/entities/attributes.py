class Attributes:
    """ The methods in this class are to be assessed from sdk.attributes, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        """
        Initialize the Attributes client.

        :param api: The API client instance for making requests
        :type api: object
        """
        self.api = api

    def add(self, source_key, name, value):
        """
        Add an attribute for an existing asset or risk.

        Creates a new attribute with the specified name and value, associated with the given
        source entity (asset or risk). The attribute key is automatically generated using
        the format #attribute#{name}#{value}#{source_key}.

        :param source_key: The key of the existing asset or risk to associate the attribute with
        :type source_key: str
        :param name: The name of the attribute (e.g., 'https', 'id', 'source')
        :type name: str
        :param value: The value of the attribute (e.g., '443', 'arn:aws:route53::123:hostedzone/Z123')
        :type value: str
        :return: The created attribute entity containing keys like 'key', 'name', 'value', 'source'
        :rtype: dict
        """
        return self.api.upsert('attribute', dict(key=source_key, name=name, value=value))['attributes'][0]

    def get(self, key):
        """
        Get details of an attribute by its exact key.

        Retrieves a specific attribute entity using its complete key. The key follows
        the format #attribute#{name}#{value}#{source_key}.

        :param key: The exact key of the attribute to retrieve
        :type key: str
        :return: The attribute entity with details like 'name', 'value', 'source', or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key)

    def delete(self, key):
        """
        Delete an attribute by its exact key.

        Removes the specified attribute from the system. The key must be the complete
        attribute key in the format #attribute#{name}#{value}#{source_key}.

        :param key: The exact key of the attribute to delete
        :type key: str
        :return: The result of the delete operation
        :rtype: dict
        """
        return self.api.delete_by_key('attribute', key)

    def list(self, prefix_filter='', source_key=None, offset=None, pages=100000) -> tuple:
        """
        List attributes with optional filtering.

        Retrieves a list of attributes, optionally filtered by a prefix or source entity.
        When source_key is provided, returns all attributes associated with that entity.
        When prefix_filter is provided, filters by the portion of the key after '#attribute#'.

        :param prefix_filter: Filter attributes by key prefix after '#attribute#'
        :type prefix_filter: str
        :param source_key: Filter attributes by their source entity (asset or risk key)
        :type source_key: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching attributes, next page offset)
        :rtype: tuple
        """
        if source_key:
            return self.api.search.by_source(source_key, 'attribute', offset, pages)
        else:
            return self.api.search.by_key_prefix(f'#attribute#{prefix_filter}', offset, pages)
