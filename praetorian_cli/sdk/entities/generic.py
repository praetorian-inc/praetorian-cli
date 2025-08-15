from praetorian_cli.sdk.model.query import Query, Node, Filter
class Generic:

    def __init__(self, api):
        self.api = api

    def get(self, key, filters=None):
        """
        Get entity by key with optional filters using graph queries.

        :param key: Entity key to retrieve
        :type key: str
        :param filters: Additional search filters as dict of field:value pairs
        :type filters: dict or None
        :return: The matching entity as arbitrary JSON
        :rtype: dict or None
        """
        query_filters = [Filter(Filter.Field.KEY, Filter.Operator.EQUAL, key)]
        
        if filters:
            for field, value in filters.items():
                try:
                    field_enum = Filter.Field(field)
                    query_filters.append(Filter(field_enum, Filter.Operator.EQUAL, value))
                except ValueError:
                    continue
        
        node = Node(filters=query_filters)
        query = Query(node=node)
        results, _ = self.api.search.by_query(query)
        return results[0] if results else None

    def list(self, label, filter_text=None, filters=None, offset=None, pages=100000):
        """
        List entities by label with optional filters.

        :param label: Label/type of entities to search for
        :type label: str
        :param filter_text: Text filter to search within entity keys
        :type filter_text: str or None
        :param filters: Additional search filters as dict of field:value pairs (not yet implemented)
        :type filters: dict or None
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        # Build the key prefix like risks does: #label#{filter}
        key_prefix = f"#{label.lower()}#{filter_text or ''}"
        return self.api.search.by_key_prefix(key_prefix, offset, pages)

    def add(self, label, entries):
        """
        Add entities with the given label and JSON entries.

        :param label: The type/label of entities to add
        :type label: str
        :param entries: Dictionary or list of dictionaries containing entity data
        :type entries: dict or list
        :return: The entities that were added
        :rtype: list
        """
        if isinstance(entries, dict):
            entries = [entries]
        
        results = []
        for entry in entries:
            # Add the type/label to the entry
            entry_with_type = entry.copy()
            entry_with_type['type'] = label
            
            # Use the API to upsert the entity
            result = self.api.upsert(label, entry_with_type)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        
        return results