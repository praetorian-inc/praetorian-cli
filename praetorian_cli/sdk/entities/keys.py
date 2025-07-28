class Keys:
    """ The methods in this class are to be assessed from sdk.keys, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, name, expires):
        """
        Add a new API key to the account.

        Creates a new API key with the specified name and expiration date. The key will be
        automatically generated and returned along with a secret for authentication.

        :param name: The name/identifier for the API key
        :type name: str
        :param expires: The expiration date in ISO 8601 format (e.g., '2024-12-31T23:59:59Z')
        :type expires: str
        :return: The created API key object containing 'key', 'name', 'secret', and other metadata
        :rtype: dict

        **Example Usage:**
            >>> # Create an API key that expires in 30 days
            >>> from datetime import datetime, timedelta
            >>> expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
            >>> key = sdk.keys.add('my-api-key', expires)
            >>> print(key['key'])  # e.g., '#key#12345678-1234-1234-1234-123456789abc'
            >>> print(key['secret'])  # The generated secret for authentication

        **Key Object Structure:**
            The returned key object contains:
            - key: Unique key identifier in format '#key#{uuid}'
            - name: The provided name for the key
            - secret: Generated secret for API authentication
            - expires: Expiration date in ISO 8601 format
            - creator: Username of the key creator
            - status: Key status (typically 'A' for active)
        """
        return self.api.force_add('key', dict(name=name, expires=expires))

    def get(self, key):
        """
        Get details of an API key by its exact key identifier.

        Retrieves the full details of an API key using its unique key identifier.
        Returns None if the key is not found or has been deleted.

        :param key: The exact key identifier in format '#key#{uuid}'
        :type key: str
        :return: The API key object if found, None otherwise
        :rtype: dict or None

        **Example Usage:**
            >>> # Get details of a specific API key
            >>> key_details = sdk.keys.get('#key#12345678-1234-1234-1234-123456789abc')
            >>> if key_details:
            ...     print(f"Key name: {key_details['name']}")
            ...     print(f"Expires: {key_details['expires']}")
            ...     print(f"Status: {key_details['status']}")

        **Key Object Structure:**
            If found, the returned object contains:
            - key: The key identifier
            - name: The key name
            - expires: Expiration date in ISO 8601 format
            - creator: Username of the key creator
            - status: Key status ('A' for active, 'D' for deleted)
            - created: Creation timestamp
        """
        return self.api.search.by_exact_key(key)

    def delete(self, key):
        """
        Delete an API key by marking it as deleted.

        Marks the specified API key as deleted, which deactivates it and prevents
        further use for authentication. The key record is retained for audit purposes.

        :param key: The exact key identifier in format '#key#{uuid}'
        :type key: str
        :return: The deleted API key object with updated status
        :rtype: dict

        **Example Usage:**
            >>> # Delete an API key
            >>> deleted_key = sdk.keys.delete('#key#12345678-1234-1234-1234-123456789abc')
            >>> print(f"Deleted key: {deleted_key['name']}")
            >>> print(f"Status: {deleted_key['status']}")  # Should be 'D' for deleted

        **Deleted Key Object:**
            The returned object contains the key with updated fields:
            - status: Changed to 'D' for deleted
            - deleted: Timestamp when the key was deleted
            - deleter: Username of the person who deleted the key
            - All other original key fields remain unchanged
        """
        return self.api.delete('key', dict(key=key), {})

    def list(self, offset=None, pages=100000) -> tuple:
        """
        List all API keys in the account with pagination support.

        Retrieves a paginated list of all API keys associated with the current account,
        including both active and deleted keys. Results are returned in chronological order.

        :param offset: The offset for pagination to retrieve a specific page of results
        :type offset: str or None
        :param pages: The maximum number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of API key objects, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all API keys
            >>> keys, next_offset = sdk.keys.list()
            >>> for key in keys:
            ...     print(f"Name: {key['name']}, Status: {key['status']}")
            
            >>> # Paginated listing
            >>> keys, next_offset = sdk.keys.list(offset=None, pages=10)
            >>> if next_offset:
            ...     more_keys, _ = sdk.keys.list(offset=next_offset, pages=10)

        **Key Object Structure:**
            Each key in the returned list contains:
            - key: Unique key identifier in format '#key#{uuid}'
            - name: The key name
            - expires: Expiration date in ISO 8601 format
            - creator: Username of the key creator
            - status: Key status ('A' for active, 'D' for deleted)
            - created: Creation timestamp
            - deleted: Deletion timestamp (if status is 'D')
            - deleter: Username who deleted the key (if status is 'D')

        **Pagination:**
            - Returns a tuple of (results, next_offset)
            - If next_offset is None, there are no more pages
            - Use the next_offset value in subsequent calls to get the next page
        """
        return self.api.search.by_key_prefix('#key#', offset, pages)
