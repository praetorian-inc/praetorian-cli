class Ports:
    """ The methods in this class are to be accessed from sdk.ports, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        """
        Initialize the Ports client.

        :param api: The API client instance for making requests
        :type api: object
        """
        self.api = api

    def get(self, key):
        """
        Get details of a port by its exact key.

        Retrieves a specific port entity using its complete key. The key follows
        the format #port#{protocol}#{port_number}#{asset_key}.

        :param key: The exact key of the port to retrieve
        :type key: str
        :return: The port entity with details like 'protocol', 'port', 'service', 'source', or None if not found
        :rtype: dict or None

        **Example Usage:**

        .. code-block:: python

            port = sdk.ports.get("#port#tcp#443#asset#example.com#example.com")
            if port:
                print(f"Port: {port['port']}")
                print(f"Protocol: {port['protocol']}")
                print(f"Service: {port['service']}")

        **Port Object Structure:**
        If found, the returned object contains:
        - key: The port identifier
        - protocol: Transport protocol (tcp/udp)
        - port: Port number (integer)
        - service: Service name (http, https, ssh, etc.)
        - source: Parent asset key
        - status: Port status ('A' for active, 'D' for deleted, etc.)
        - created: Creation timestamp
        - visited: Last seen timestamp
        - username: Username associated with the port
        - ttl: Time-to-live timestamp
        """
        return self.api.search.by_exact_key(key)

    def list(self, prefix_filter='', source_key=None, offset=None, pages=1) -> tuple:
        """
        List ports with optional filtering.

        Retrieves a list of ports, optionally filtered by a prefix or source entity.
        When source_key is provided, returns all ports associated with that asset.
        When prefix_filter is provided, filters by the portion of the key after '#port#'.

        :param prefix_filter: Filter ports by key prefix after '#port#' (e.g., 'tcp#443', 'udp#53')
        :type prefix_filter: str
        :param source_key: Filter ports by their source asset key
        :type source_key: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching ports, next page offset)
        :rtype: tuple

        **Example Usage:**

        .. code-block:: python

            # List all ports
            ports, next_offset = sdk.ports.list()
            
            # Filter ports by protocol and port number
            https_ports, _ = sdk.ports.list(prefix_filter="tcp#443")
            
            # List ports for a specific asset
            asset_ports, _ = sdk.ports.list(source_key="#asset#example.com#example.com")
            
            # Paginated listing
            ports, next_offset = sdk.ports.list(prefix_filter="tcp", pages=10)
            if next_offset:
                more_ports, _ = sdk.ports.list(prefix_filter="tcp", offset=next_offset, pages=10)

        **Filtering Examples:**
        - prefix_filter="tcp" matches all TCP ports
        - prefix_filter="tcp#443" matches HTTPS ports specifically
        - prefix_filter="udp#53" matches DNS ports specifically

        **Port List Structure:**
        Each port in the returned list contains:
        - key: Unique port identifier in format '#port#{protocol}#{port}#{asset_key}'
        - protocol: Transport protocol (tcp/udp)
        - port: Port number (integer)
        - service: Service name (http, https, ssh, etc.) if identified
        - source: Parent asset key
        - status: Port status ('A' for active, 'F' for frozen, etc.)
        - created: Creation timestamp
        - visited: Last seen timestamp
        - username: Username associated with the port
        - ttl: Time-to-live timestamp

        **Pagination:**
        - Returns a tuple of (results, next_offset)
        - If next_offset is None, there are no more pages
        - Use the next_offset value in subsequent calls to get the next page
        """
        if source_key:
            return self.api.search.by_source(source_key, entity_type='port', offset=offset, pages=pages)
        else:
            return self.api.search.by_prefix('port', prefix_filter, offset=offset, pages=pages)