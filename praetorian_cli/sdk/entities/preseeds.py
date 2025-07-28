from praetorian_cli.handlers.utils import error


class Preseeds:
    """ The methods in this class are to be assessed from sdk.preseeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        """
        Initialize the Preseeds client.

        :param api: The API client instance for making requests
        :type api: object
        """
        self.api = api

    def add(self, type, title, value, status):
        """
        Add a new preseed for automated asset discovery.

        Creates a preseed that serves as a discovery pattern to generate seeds for asset
        enumeration. The preseed key is automatically generated using the format
        #preseed#{type}#{title}#{value}.

        :param type: The type of preseed (e.g., 'domain', 'subdomain', 'ip')
        :type type: str
        :param title: The title or name of the preseed for identification
        :type title: str
        :param value: The value or pattern for the preseed (e.g., domain name, IP range)
        :type value: str
        :param status: The status of the preseed. Valid values: 'A' (ACTIVE), 'F' (FROZEN), 'D' (DELETED), 'P' (PENDING), 'FR' (FROZEN_REJECTED)
        :type status: str
        :return: The created preseed entity containing keys like 'key', 'type', 'title', 'value', 'status'
        :rtype: dict
        """
        return self.api.force_add('preseed', dict(type=type, title=title, value=value, status=status))

    def get(self, key, details=False):
        """
        Get details of a preseed by its exact key.

        Retrieves a specific preseed entity using its complete key. The key follows
        the format #preseed#{type}#{title}#{value}.

        :param key: The exact key of the preseed to retrieve
        :type key: str
        :param details: Whether to include additional details in the response
        :type details: bool
        :return: The preseed entity with details like 'type', 'title', 'value', 'status', or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key, details)

    def update(self, key, status):
        """
        Update a preseed's status.

        Updates the status of an existing preseed. Only the status field can be updated
        for preseeds. The preseed must exist before it can be updated.

        :param key: The exact key of the preseed to update in format #preseed#{type}#{title}#{value}
        :type key: str
        :param status: The new status for the preseed. Valid values: 'A' (ACTIVE), 'F' (FROZEN), 'D' (DELETED), 'P' (PENDING), 'FR' (FROZEN_REJECTED)
        :type status: str
        :return: The updated preseed entity or None if preseed not found
        :rtype: dict or None
        """
        preseed = self.api.search.by_exact_key(key)
        if preseed:
            return self.api.update('preseed', dict(key=key, status=status))
        else:
            error(f'Pre-seed {key} is not found.')

    def delete(self, key):
        """
        Delete a preseed by its exact key.

        Removes the specified preseed from the system. The key must be the complete
        preseed key in the format #preseed#{type}#{title}#{value}.

        :param key: The exact key of the preseed to delete
        :type key: str
        :return: The result of the delete operation
        :rtype: dict
        """
        return self.api.delete_by_key('preseed', key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List preseeds with optional filtering.

        Retrieves a list of preseeds, optionally filtered by a prefix. When prefix_filter
        is provided, it filters by the portion of the key after '#preseed#'. This allows
        filtering by type, title, or other key components.

        :param prefix_filter: Filter preseeds by key prefix after '#preseed#' (e.g., 'domain' to filter by type)
        :type prefix_filter: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching preseeds, next page offset)
        :rtype: tuple
        """
        return self.api.search.by_key_prefix(f'#preseed#{prefix_filter}', offset, pages)
