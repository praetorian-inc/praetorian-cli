from praetorian_cli.handlers.utils import error


class Preseeds:
    """ The methods in this class are to be assessed from sdk.preseeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, type, title, value, status):
        """Add a preseed to the Chariot database.
        
        Preseeds are adjacent domain discovery patterns used for automated asset discovery.
        They represent potential seeds that can be activated for domain enumeration and
        reconnaissance activities. Preseeds cannot be added with PENDING status and
        default to ACTIVE when created.

        :param type: The type/category of the preseed (e.g., "whois+company", "dns+subdomain")
        :type type: str
        :param title: A human-readable title or name for the preseed
        :type title: str
        :param value: The actual value or pattern for the preseed
        :type value: str
        :param status: The status of the preseed. Valid values are:
                      - 'A' (ACTIVE): Preseed is active and available for discovery
                      - 'F' (FROZEN): Preseed is temporarily disabled
                      - 'D' (DELETED): Preseed is marked for deletion
                      - 'FR' (FROZEN_REJECTED): Preseed is frozen and rejected
                      Note: Preseeds cannot be created with 'P' (PENDING) status
        :type status: str
        :return: The created preseed object with generated key and metadata
        :rtype: dict

        **Example Usage:**
        
        .. code-block:: python
        
            sdk.preseeds.add(
                type="whois+company",
                title="Example Company", 
                value="example company",
                status="A"
            )
            
            sdk.preseeds.add(
                type="dns+subdomain",
                title="API Subdomain",
                value="api.example.com", 
                status="A"
            )

        **Key Format:**
        The generated preseed key follows the format: #preseed#{type}#{title}#{value}
        """
        return self.api.force_add('preseed', dict(type=type, title=title, value=value, status=status))

    def get(self, key, details=False):
        """Retrieve details of a specific preseed by its key.
        
        Fetches comprehensive information about a preseed including its type, title,
        value, status, and optionally additional details like creation metadata.

        :param key: The unique key identifier of the preseed in the format:
        :type key: str
        :param details: Whether to retrieve additional detailed information about the preseed
        :type details: bool
        :return: Dictionary containing preseed information including type, title, value,
                status, and optionally additional metadata if details=True
        :rtype: dict

        **Example Usage:**
        
        .. code-block:: python
        
            preseed = sdk.preseeds.get("#preseed#whois+company#Example Company#example company")
            
            detailed_preseed = sdk.preseeds.get(
                "#preseed#whois+company#Example Company#example company",
                details=True
            )

        **Key Format:**
        Preseed keys follow the format: #preseed#{type}#{title}#{value}
        """
        return self.api.search.by_exact_key(key, details)

    def update(self, key, status):
        """Update the status of an existing preseed.
        
        Only the status field can be meaningfully updated for preseeds. This allows
        you to activate, freeze, or mark preseeds for deletion without recreating them.
        The preseed must exist before it can be updated.

        :param key: The unique key identifier of the preseed in the format:
        :type key: str
        :param status: The new status for the preseed. Valid values are:
                      - 'A' (ACTIVE): Preseed is active and available for discovery
                      - 'F' (FROZEN): Preseed is temporarily disabled
                      - 'D' (DELETED): Preseed is marked for deletion
                      - 'FR' (FROZEN_REJECTED): Preseed is frozen and rejected
                      - 'P' (PENDING): Preseed is pending activation
        :type status: str
        :return: The updated preseed object with new status
        :rtype: dict
        :raises: Prints error message if preseed with the specified key is not found

        **Example Usage:**
        
        .. code-block:: python
        
            sdk.preseeds.update(
                "#preseed#whois+company#Example Company#example company",
                "A"
            )
            
            sdk.preseeds.update(
                "#preseed#dns+subdomain#API Subdomain#api.example.com",
                "F"
            )
            
            sdk.preseeds.update(
                "#preseed#whois+company#Old Company#old company",
                "D"
            )

        **Note:**
        Only the status field can be updated. To change type, title, or value,
        you must delete the existing preseed and create a new one.
        """
        preseed = self.api.search.by_exact_key(key)
        if preseed:
            return self.api.update('preseed', dict(key=key, status=status))
        else:
            error(f'Pre-seed {key} is not found.')

    def delete(self, key):
        """Delete a preseed from the Chariot database.
        
        Permanently removes the preseed from the system. This is different from
        updating the status to 'D' (DELETED), as this operation completely
        removes the preseed record.

        :param key: The unique key identifier of the preseed in the format:
        :type key: str
        :return: Result of the deletion operation
        :rtype: dict

        **Example Usage:**
        
        .. code-block:: python
        
            sdk.preseeds.delete("#preseed#whois+company#Example Company#example company")
            
            sdk.preseeds.delete("#preseed#dns+subdomain#API Subdomain#api.example.com")

        **Key Format:**
        Preseed keys follow the format: #preseed#{type}#{title}#{value}
        
        **Note:**
        This permanently removes the preseed. To temporarily disable a preseed,
        consider using update() with status 'F' (FROZEN) instead.
        """
        return self.api.delete_by_key('preseed', key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """List preseeds with optional filtering and pagination.
        
        Retrieves a list of preseeds from the Chariot database. Results can be
        filtered by type prefix and paginated for large datasets. This is useful
        for discovering existing preseeds and managing discovery patterns.

        :param prefix_filter: Optional filter to match preseed types. Only preseeds
                             whose type starts with this prefix will be returned.
                             Empty string returns all preseeds.
        :type prefix_filter: str
        :param offset: Starting position for pagination. Use None to start from beginning.
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve. Each page contains multiple preseeds.
        :type pages: int
        :return: Tuple containing (list_of_preseeds, next_offset_for_pagination)
                The first element is a list of preseed dictionaries, the second is
                the offset to use for the next page of results.
        :rtype: tuple[list[dict], str]

        **Example Usage:**
        
        .. code-block:: python
        
            preseeds, next_offset = sdk.preseeds.list()
            
            whois_preseeds, _ = sdk.preseeds.list(prefix_filter="whois")
            
            dns_preseeds, next_offset = sdk.preseeds.list(
                prefix_filter="dns",
                pages=10
            )
            
            more_preseeds, _ = sdk.preseeds.list(
                prefix_filter="dns",
                offset=next_offset,
                pages=10
            )

        **Filtering:**
        The prefix_filter matches against the preseed type field. For example:
        - prefix_filter="whois" matches "whois+company", "whois+email", etc.
        - prefix_filter="dns" matches "dns+subdomain", "dns+zone", etc.
        - prefix_filter="" matches all preseeds
        
        **Return Format:**
        Each preseed in the returned list contains fields like:
        - key: The unique preseed identifier
        - type: The preseed type/category
        - title: Human-readable title
        - value: The preseed value/pattern
        - status: Current status ('A', 'F', 'D', 'P', 'FR')
        """
        return self.api.search.by_key_prefix(f'#preseed#{prefix_filter}', offset, pages)
