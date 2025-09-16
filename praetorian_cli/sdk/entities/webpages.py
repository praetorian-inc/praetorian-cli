from praetorian_cli.sdk.model.query import Query, Node, Filter


class Webpages:
    """ The methods in this class are to be accessed from sdk.webpages, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """
        Get details of a webpage by key.

        :param key: Entity key in format #webpage#{url}
        :type key: str
        :return: The webpage matching the specified key
        :rtype: dict
        """
        return self.api.search.by_exact_key(key)

    def list(self, key_prefix='', pages=100000) -> tuple:
        """
        List webpages.

        :param key_prefix: Supply this to perform prefix-filtering of the webpage key. E.g., '#webpage#https://example.com'
        :type key_prefix: str
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of webpages, next page offset)
        :rtype: tuple
        """
        # Use Node.Label.ASSET as webpages are a type of asset
        query = Query(
            node=Node(
                labels=['Webpage'],
                filters=[
                    Filter(Filter.Field.KEY, Filter.Operator.STARTS_WITH, key_prefix)
                ] if key_prefix else None
            ),
            limit=100
        )
        
        return self.api.search.by_query(query, pages)

    def link_source(self, webpage_key, entity_key):
        """
        Link a file or repository to a webpage as source code.

        :param webpage_key: The webpage key in format #webpage#{url}
        :type webpage_key: str
        :param entity_key: The entity key (file or repository) to link. Format: #file#{path} or #repository#{url}#{name}
        :type entity_key: str
        :return: The response from the API
        :rtype: dict
        """
        data = {
            'webpageKey': webpage_key,
            'entityKey': entity_key
        }
        
        resp = self.api._make_request('PUT', self.api.url('/webpage/link'), json=data)
        
        if resp.status_code != 200:
            raise Exception(f"Failed to link source: [{resp.status_code}] {resp.text}")
            
        return resp.json()

    def unlink_source(self, webpage_key, entity_key):
        """
        Unlink a file or repository from a webpage's source code.

        :param webpage_key: The webpage key in format #webpage#{url}
        :type webpage_key: str
        :param entity_key: The entity key (file or repository) to unlink. Format: #file#{path} or #repository#{url}#{name}
        :type entity_key: str
        :return: The response from the API
        :rtype: dict
        """
        data = {
            'webpageKey': webpage_key,
            'entityKey': entity_key
        }
        
        resp = self.api._make_request('DELETE', self.api.url('/webpage/link'), json=data)
        
        if resp.status_code != 200:
            raise Exception(f"Failed to unlink source: [{resp.status_code}] {resp.text}")
            
        return resp.json()