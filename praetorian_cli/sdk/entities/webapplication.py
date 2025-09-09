from praetorian_cli.sdk.model.query import Query, Node, Filter


class WebApplication:
    """The methods in this class are to be accessed from sdk.webapplication, where sdk
    is an instance of Chariot."""

    def __init__(self, api):
        self.api = api

    def add(self, url, name=None):
        """
        Add a WebApplication seed to the Chariot database.

        WebApplications are created as seeds with type 'webapplication' in the backend. This
        method creates a new WebApplication asset that will be discovered and
        analyzed by Chariot's web application scanning capabilities.

        :param url: The primary URL of the web application
        :type url: str
        :param name: Optional name for the web application (defaults to URL if not provided)
        :type name: str or None
        :return: The created WebApplication seed object
        :rtype: dict
        :raises Exception: If the URL is invalid or the request fails

        **Example Usage:**
            >>> # Add a web application with URL only
            >>> webapp = sdk.webapplication.add("https://app.example.com")

            >>> # Add a web application with custom name
            >>> webapp = sdk.webapplication.add("https://app.example.com", 
            ...                         name="Example App Portal")

        **WebApplication Object Structure:**
            The returned WebApplication object contains:
            - key: WebApplication identifier in format #webapplication#{url}
            - dns: Domain extracted from the URL
            - name: Display name for the application
            - status: Asset status (typically 'A' for active)
            - class: Asset class set to 'webapplication'
            - created: Creation timestamp
            - labels: List including 'Seed' label
        """
        if not url:
            raise Exception("URL is required for WebApplication")
        
        if not name:
            name = url

        payload = {
            'type': 'webapplication',
            'model': {
                'url': url,
                'name': name,
                'status': 'A'  # Active status
            }
        }

        return self.api.upsert('seeds/webapps', payload)

    def get(self, key):
        """
        Get details of a specific WebApplication by its key.

        :param key: The WebApplication key in format #asset#webapp#{url}#{url}
        :type key: str
        :return: WebApplication object with detailed information, or None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> # Get a specific WebApplication
            >>> webapp = sdk.webapplication.get(
            ...     "#asset#webapp#https://app.example.com#https://app.example.com")

        **WebApplication Object Structure:**
            The returned WebApplication object contains:
            - key: WebApplication identifier
            - dns: Domain from the URL
            - name: Display name
            - status: Current status ('A', 'P', etc.)
            - class: Asset class ('webapp')
            - url: Primary URL of the application
            - attributes: List of associated attributes
            - risks: List of associated risks (if details requested)
            - created: Creation timestamp
            - updated: Last update timestamp
        """
        return self.api.search.by_exact_key(key)

    def list(self, filter=None, offset=0, pages=100000) -> tuple:
        """
        List WebApplications, optionally filtered by query or host.

        Retrieve WebApplication assets with optional filtering capabilities. Filters
        can be applied to search by URL components, names, or host domains.

        :param query_filter: General filter applied to WebApplication URLs and names
        :type query_filter: str
        :param host_filter: Filter WebApplications by specific host/domain
        :type host_filter: str
        :param offset: The offset for pagination to retrieve a specific page of results
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve (default: 100000 for all results)
        :type pages: int
        :return: A tuple containing (list of matching WebApplications, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all WebApplications
            >>> webapps, offset = sdk.webapplication.list()

            >>> # Filter WebApplications by URL/name
            >>> webapps, offset = sdk.webapplication.list(query_filter="admin")

            >>> # Filter WebApplications by host domain
            >>> webapps, offset = sdk.webapplication.list(host_filter="example.com")

            >>> # Combined filtering
            >>> webapps, offset = sdk.webapplication.list(
            ...     query_filter="portal", host_filter="app.example.com")

            >>> # Get first page with pagination
            >>> webapps, offset = sdk.webapplication.list("", "", None, 1)

        **WebApplication Filtering:**
            - query_filter: Searches in WebApplication URLs and names
            - host_filter: Filters by the domain/host portion of URLs
            - Filters can be combined for more precise results
        """
        filters = []
        if filter:
            filters.append(Filter(field=Filter.Field.PRIMARY_URL, operator=Filter.Operator.CONTAINS, value=filter))
        node = Node(labels=[Node.Label.WEBAPPLICATION], filters=filters)
        query = Query(node=node, page=offset, limit=pages)
        return self.api.search.by_query(query, pages)