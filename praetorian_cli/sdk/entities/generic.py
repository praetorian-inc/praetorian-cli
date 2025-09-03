from praetorian_cli.sdk.model.query import Query, Node, Filter
class Generic:

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """
        Get entity by key 

        :param key: Entity key to retrieve
        :type key: str
        :return: The matching entity as arbitrary JSON
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key)

    def list(self, label, prefix_filter=None, offset=None, pages=100000):
        """
        List entities by label with optional filters.

        :param label: Label/type of entities to search for
        :type label: str
        :param prefix_filter: Text filter to search within entity keys
        :type prefix_filter: str or None
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.api.search.by_key_prefix(f"#{label.lower()}#{prefix_filter or ''}", offset, pages)

    def add(self, entries):
        """
        Add a new object with the given JSON entries.
        Currently only supports Assetlike objects.

        :param entries: Dictionary or list of dictionaries containing entity data
        :type entries: dict or list
        :return: The entities that were added
        :rtype: list
        """
        return self.api.upsert('model', entries)

    def get_schema(self, entity_type: str = None) -> dict:
        """Get schema information for entity types
        
        Args:
            entity_type: Optional specific entity type, if None returns all schemas
            
        Returns:
            dict: Schema information
        """
        result = self.api.get('schema')
        if entity_type:
            if entity_type not in result:
                return {}
            return {entity_type: result[entity_type]}
        return result
