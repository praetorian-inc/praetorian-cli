from praetorian_cli.sdk.model.query import Query, Node, Filter, Relationship


class Webpage:
    """The methods in this class are to be accessed from sdk.webpage, where sdk
    is an instance of Chariot."""

    def __init__(self, api):
        self.api = api

    def add(self, url, parent_key=None):
        """
        Add a Webpage to the Chariot database.

        WebPages represent individual pages or endpoints that can be optionally
        associated with a parent WebApplication. The backend uses a WebpageRequest
        structure with embedded webpage data and optional parent key.

        :param url: The full URL of the page
        :type url: str
        :param parent_key: Optional key of the parent WebApplication 
        :type webapp_key: str or None
        :return: The created WebPage object
        :rtype: dict
        :raises Exception: If the URL is invalid or the request fails

        **Example Usage:**
            >>> # Add a simple page without parent
            >>> page = sdk.webpage.add("https://app.example.com/login")

            >>> # Add a page with parent WebApplication
            >>> page = sdk.webpage.add(
            ...     url="https://app.example.com/admin",
            ...     parent_key="#webapplication#https://app.example.com")

        **WebPage Object Structure:**
            The returned Webpage object contains:
            - key: Webpage identifier in format #webpage#{url}
            - url: Full URL of the page
            - status: Current status
            - parent: Parent WebApplication relationship (if applicable)
            - created: Creation timestamp
        """
        if not url:
            raise Exception("URL is required for Webpage")

        if parent_key and not parent_key.startswith('#webapplication#'):
            raise Exception("Invalid WebApplication key format")

        payload = {
            'webpage': {
                'url': url,
                'status': 'A'  # Active status
            }
            
        }

        if parent_key:
            payload['parent_key'] = parent_key

        return self.api.post('webpage', payload)

    def get(self, key):
        """
        Get details of a specific Webpage by its key.

        :param key: The WebPage key identifier
        :type key: str
        :return: Webpage object with detailed information, or None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> # Get a specific Webpage
            >>> page = sdk.webpage.get("webpage_key_123")

        **Webpage Object Structure:**
            The returned Webpage object contains:
            - key: Webpage identifier
            - url: Full URL of the page
            - created: Creation timestamp
            - updated: Last update timestamp
        """
        query = Query(node=Node(labels=[Node.Label.WEBPAGE], filters=[Filter(field=Filter.Field.KEY, operator=Filter.Operator.EQUAL, value=key)]))
        return self.api.search.by_query(query)[0][0]

    def list(self, parent_key=None, filter=None, offset=0, pages=100000) -> tuple:
        """
        List Webpages, optionally filtered by parent WebApplication.

        Retrieve Webpage entities with optional filtering capabilities. Can filter by
        parent WebApplication.

        :param parent_key: Filter pages by specific WebApplication (optional)
        :type parent_key: str or None
        :param filter: Filter pages by specific URL (optional)
        :type filter: str or None
        :param offset: The offset for pagination to retrieve a specific page of results
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve (default: 100000 for all results)
        :type pages: int
        :return: A tuple containing (list of matching Webpages, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all WebPages
            >>> pages, offset = sdk.webpage.list()

            >>> # List pages for specific WebApplication
            >>> pages, offset = sdk.webpage.list(
            ...     webapp_key="#asset#webapp#https://app.example.com#https://app.example.com")

        **WebPage Filtering:**
            - parent_key: Filters by parent WebApplication
            - filter: Filters by specific URL
        """
        if parent_key and not parent_key.startswith('#webapplication#'):
            raise Exception("Invalid WebApplication key format")

        relationships = []
        filters = []
        if parent_key:
            parentFilter = Filter(field=Filter.Field.KEY, operator=Filter.Operator.EQUAL, value=parent_key)
            relationship = Relationship(label=Relationship.Label.HAS_WEBPAGE, target=Node(labels=[Node.Label.WEBAPPLICATION], filters=[parentFilter]))
            relationships.append(relationship)
        if filter:
            urlFilter = Filter(field=Filter.Field.KEY, operator=Filter.Operator.CONTAINS, value=filter)
            filters.append(urlFilter)
        node = Node(labels=[Node.Label.WEBPAGE], filters=filters, relationships=relationships)
        query = Query(node=node, page=offset)
        return self.api.search.by_query(query, pages)

    def delete(self, key):
        """
        Delete a webpage by its key.

        :param key: The WebPage key identifier
        :type key: str
        """
        body = {
            'webpage': {
                'key': key
            }
        }
        self.api.delete('webpage', params={}, body=body)

    def link_source(self, webpage_key, entity_key):
        """
        Link a file or repository to a webpage as source code.

        :param webpage_key: The webpage key in format #webpage#{url}
        :type webpage_key: str
        :param entity_key: The entity key (file or repository) to link. Format: #file#{path} or #repository#{url}#{name}
        :type entity_key: str
        :return: The updated webpage with linked artifacts
        :rtype: dict
        """
        data = {
            'webpageKey': webpage_key,
            'entityKey': entity_key
        }
        
        return self.api.put('webpage/link', data, {})

    def unlink_source(self, webpage_key, entity_key):
        """
        Unlink a file or repository from a webpage's source code.

        :param webpage_key: The webpage key in format #webpage#{url}
        :type webpage_key: str
        :param entity_key: The entity key (file or repository) to unlink. Format: #file#{path} or #repository#{url}#{name}
        :type entity_key: str
        :return: The updated webpage with artifacts removed
        :rtype: dict
        """
        data = {
            'webpageKey': webpage_key,
            'entityKey': entity_key
        }
    
        return self.api.delete('webpage/link', data, {})