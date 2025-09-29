import json
from praetorian_cli.sdk.model.query import Query
from praetorian_cli.sdk.model.globals import EXACT_FLAG, DESCENDING_FLAG, GLOBAL_FLAG, USER_FLAG, Kind
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

    def by_key_prefix(self, key_prefix, offset=None, pages=100000, user=False) -> tuple:
        """
        Search for entities by key prefix. <mcp>If the response is too large, make your query more specific.<mcp>

        :param key_prefix: The prefix of the entity key to search for
        :type key_prefix: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(key_prefix, None, offset, pages, user=user)

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
        Search for entities by source key. <mcp>If the response is too large, make your query more specific.<mcp>

        :param source: The source key to search for
        :type source: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'source:{source}', kind, offset, pages)

    def by_status(self, status_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by status prefix. <mcp>If the response is too large, make your query more specific.<mcp>

        :param status_prefix: The status prefix to search for (e.g., 'OH', 'TH')
        :type status_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'status:{status_prefix}', kind, offset, pages)

    def by_name(self, name_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by name prefix. <mcp>If the response is too large, make your query more specific.<mcp>

        :param name_prefix: The name prefix to search for
        :type name_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'name:{name_prefix}', kind, offset, pages)

    def by_dns(self, dns_prefix, kind, offset=None, pages=100000) -> tuple:
        """
        Search for entities by DNS prefix. <mcp>If the response is too large, make your query more specific.<mcp>

        :param dns_prefix: The DNS prefix to search for
        :type dns_prefix: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple
        """
        return self.by_term(f'dns:{dns_prefix}', kind, offset, pages)

    def by_term(self, search_term, kind=None, offset=None, pages=100000, exact=False, descending=False,
                global_=False, user=False) -> tuple:
        """
        Search for a given kind by term.

        :param search_term: Either an entity key, starting with #, or a column:value pair, ie dns:praetorian.com
        :type search_term: str
        :param kind: Kind of the entity, ie Asset
        :type kind: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
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
        if user:
            params |= USER_FLAG

        results = self.api.my(params, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset

    def by_query(self, query, pages=100000) -> tuple:
        """
        Search for entities using a graph query.

        The Chariot graph query system allows you to search and retrieve data from the Neo4j 
        graph database using a structured JSON format. This enables complex queries across 
        relationships between assets, vulnerabilities, attributes, and other entities.

        :param query: The graph query object to execute
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching entities, next page offset)
        :rtype: tuple

        **Query Structure**

        A graph query is a JSON object with the following structure::

            {
              "node": {
                // Root node definition (required)
              },
              "page": 0,           // Pagination page number (optional, default: 0)
              "limit": 100,        // Results per page (optional, default: 100)
              "orderBy": "name",   // Field to sort by (optional)
              "descending": false  // Sort order (optional, default: false)
            }

        **Node Structure**

        The ``node`` object defines a node in the graph and conditions to apply to it::

            {
              "labels": ["Asset", "Attribute"],  // Node types to match (optional)
              "filters": [                       // Property filters (optional)
                {
                  "field": "status",
                  "operator": "=",
                  "value": "A"
                }
              ],
              "relationships": []                // Related nodes (optional)
            }

        **Available Entity Types**

        **Node Labels:**
        
        - ``Asset``: Infrastructure entities (hosts, services, domains)
        - ``Risk``: Security vulnerabilities and findings  
        - ``Attribute``: Key-value metadata attached to entities
        - ``Technology``: Software/services running on assets
        - ``Credential``: Authentication data

        **Relationship Types:**
        
        - ``DISCOVERED``: Discovery relationships between entities
        - ``HAS_VULNERABILITY``: Links assets to security risks
        - ``HAS_ATTRIBUTE``: Links entities to their metadata
        - ``HAS_TECHNOLOGY``: Links assets to technologies they run
        - ``HAS_CREDENTIAL``: Links entities to credentials

        **Filter Operations**

        Filters define conditions on node properties::

            {
              "field": "name",                   // Property name to filter on
              "operator": "=",                   // Comparison operator
              "value": "example.com",            // Value to compare against
              "not": false                       // Whether to negate (optional)
            }

        **Supported Operators:**
        
        - ``=``: Exact match
        - ``<``, ``>``, ``<=``, ``>=``: Numeric comparisons  
        - ``CONTAINS``: String contains substring
        - ``STARTS WITH``: String starts with prefix
        - ``ENDS WITH``: String ends with suffix
        - ``IN``: Value is in provided list

        **Multiple Values:**
        
        You can provide an array of values, which are OR'd together::

            {
              "field": "name",
              "operator": "=", 
              "value": ["example.com", "test.com"]  // Matches either value
            }

        Multiple filters on a node are AND'd together.

        **Relationship Structure**

        Relationships define connections between nodes::

            {
              "label": "HAS_ATTRIBUTE",    // Relationship type
              "source": { /* Node */ },    // Source node (only set if target is parent)
              "target": { /* Node */ },    // Target node (only set if source is parent)
              "optional": false            // Whether relationship is required (optional)
            }

        Only one of ``source`` or ``target`` should be set. The parent node in the structure 
        is assumed to be the other end of the relationship.

        **Examples**

        **Find active assets with an open SSH port:**

        .. code-block:: python

            from praetorian_cli.sdk.model.query import Query, Node, Filter, Relationship
            
            query = Query(
                node=Node(
                    labels=["Asset"],
                    filters=[
                        Filter(field="status", operator="=", value="A")
                    ],
                    relationships=[
                        Relationship(
                            label="HAS_ATTRIBUTE",
                            target=Node(
                                labels=["Attribute"],
                                filters=[
                                    Filter(field="name", operator="=", value="port"),
                                    Filter(field="value", operator="=", value="22")
                                ]
                            )
                        )
                    ]
                )
            )
            
            results, offset = search.by_query(query)

        **Find assets with high/critical vulnerabilities:**

        .. code-block:: python

            query = Query(
                node=Node(
                    labels=["Asset"],
                    relationships=[
                        Relationship(
                            label="HAS_VULNERABILITY", 
                            target=Node(
                                labels=["Risk"],
                                filters=[
                                    Filter(field="priority", operator="<=", value=10)
                                ]
                            )
                        )
                    ]
                )
            )
            
            results, offset = search.by_query(query)

        **Complex query - IPv6 cloud assets with critical risks:**

        .. code-block:: python

            query = Query(
                node=Node(
                    labels=["Asset"],
                    filters=[
                        Filter(field="class", operator="=", value="ipv6")
                    ],
                    relationships=[
                        Relationship(
                            label="HAS_ATTRIBUTE",
                            target=Node(
                                labels=["Attribute"], 
                                filters=[
                                    Filter(field="name", operator="IN", 
                                          value=["amazon", "azure", "gcp"])
                                ]
                            )
                        ),
                        Relationship(
                            label="HAS_VULNERABILITY",
                            target=Node(
                                labels=["Risk"],
                                filters=[
                                    Filter(field="priority", operator="=", value=0)
                                ]
                            )
                        )
                    ]
                )
            )

        **Multi-relationship traversal - Assets connected to technologies:**

        .. code-block:: python

            query = Query(
                node=Node(
                    labels=["Asset"],
                    relationships=[
                        Relationship(
                            label="DISCOVERED",
                            target=Node(
                                labels=["Asset"],
                                relationships=[
                                    Relationship(
                                        label="HAS_TECHNOLOGY",
                                        target=Node(
                                            labels=["Technology"],
                                            filters=[
                                                Filter(field="name", operator="CONTAINS", value="nginx")
                                            ]
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
            )

        **Best Practices**

        1. **Start with specific nodes**: Begin with the most specific node type and add 
           relationships to narrow results.

        2. **Use labels**: Always specify node labels when possible to improve query performance.

        3. **Limit results**: Use pagination (``pages`` parameter) for large result sets.

        4. **Filter early**: Apply filters at the highest level possible in the query structure.

        5. **Use optional relationships**: When a relationship might not exist but you still 
           want to include the node, set ``optional: true``.

        6. **Combine filters efficiently**: Use ``IN`` operator for multiple values instead of 
           multiple separate filters when possible.

        7. **Order results**: Use ``orderBy`` and ``descending`` parameters to control result ordering.
        """
        if type(query) == Query:
            results = self.api.my_by_query(query, pages)
        else:
            results = self.api.my_by_raw_query(json.loads(query), pages)

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
