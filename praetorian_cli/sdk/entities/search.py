from praetorian_cli.sdk.model.query import Query
from praetorian_cli.sdk.model.globals import EXACT_FLAG, DESCENDING_FLAG, GLOBAL_FLAG, Kind
class Search:

    def __init__(self, api):
        self.api = api

    def count(self, search_term) -> {}:
        """
        Get count statistics for a search term.

        :param search_term: The search term to count matches for
        :type search_term: str
        :return: Dictionary containing count statistics
        :rtype: dict
        """
        return self.api.count(dict(key=search_term))

    def by_key_prefix(self, key_prefix, offset=None, pages=100000) -> tuple:
        """
        Search for entities by key prefix.

        :param key_prefix: The prefix of the entity key to search for
        :type key_prefix: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(key_prefix, None, offset, pages)

    def by_exact_key(self, key, get_attributes=False) -> {}:
        """
        Get an entity by its exact key.

        :param key: The exact key of the entity to retrieve
        :type key: str
        :param get_attributes: Whether to also retrieve associated attributes
        :type get_attributes: bool
        :return: The matching entity or None if not found
        :rtype: dict or None
        """
        hits, _ = self.by_term(key, exact=True)
        hit = hits[0] if hits else None
        if get_attributes and hit:
            attributes, _ = self.by_source(key, Kind.ATTRIBUTE.value)
            hit['attributes'] = attributes
        return hit

    def by_source(self, source, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by source key.

        :param source: The source key to search for
        :type source: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'source:{source}', kind, offset, pages)

    def by_status(self, status_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by status prefix.

        :param status_prefix: The status prefix to search for (e.g., 'OH', 'TH')
        :type status_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'status:{status_prefix}', kind, offset, pages)

    def by_name(self, name_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by name prefix.

        :param name_prefix: The name prefix to search for
        :type name_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'name:{name_prefix}', kind, offset, pages)

    def by_dns(self, dns_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by DNS prefix.

        :param dns_prefix: The DNS prefix to search for
        :type dns_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'dns:{dns_prefix}', kind, offset, pages)

    def by_term(self, search_term, kind=None, offset=None, pages=100000, exact=False, descending=False,
                global_=False) -> tuple:
        """
        Search for a given kind by term.

        :param search_term: Either an entity key, starting with #, or a column:value pair, ie dns:praetorian.com
        :type search_term: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :param exact: Whether to perform exact key matching
        :type exact: bool
        :param descending: Return data in descending order
        :type descending: bool
        :param global_: Use the global data set
        :type global_: bool
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        params = dict(key=search_term)
        if kind:
            params |= dict(label=kind)
        if offset:
            params |= dict(offset=offset)
        if exact:
            params |= EXACT_FLAG
        if descending:
            params |= DESCENDING_FLAG
        if global_:
            params |= GLOBAL_FLAG

        results = self.api.my(params, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset

    def by_query(self, query: Query, pages=100000, offset=None) -> tuple:
        """
        Search for entities using a graph query.

        :param query: The graph query object to execute
        :type query: Query
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        results = self.api.my_by_query(query, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset


def flatten_results(results):
    if isinstance(results, list):
        return results
    flattened = []
    for key in results.keys():
        flattened.extend(flatten_results(results[key]))
    return flattened
