from typing import List

EXACT_FLAG = {'exact': 'true'}
DESCENDING_FLAG = {'desc': 'true'}
GLOBAL_FLAG = {'global': 'true'}


class Filter:

    def __init__(self, field: str, operator: str, value: str):
        self.field = field
        self.operator = operator
        self.value = value

    def to_dict(self) -> dict:
        return dict(field=self.field, operator=self.operator, value=self.value)


class Node:

    def __init__(self, labels: List[str], filters: List[Filter], relationships: List['Relationship']):
        self.labels = labels
        self.filters = filters
        self.relationships = relationships

    def to_dict(self):
        ret = dict()
        if self.labels:
            ret |= dict(labels=self.labels)
        if self.filters:
            ret |= dict(filters=[x.to_dict() for x in self.filters])
        if self.relationships:
            ret |= dict(relationships=[x.to_dict() for x in self.relationships])
        return ret


class Relationship:

    def __init__(self, label: str, source: Node, Target: Node):
        self.label = label
        self.source = source
        self.target = target

        def to_dict(self):
            ret = dict(label=self.label)
            if self.source:
                ret |= dict(source=self.source.to_dict())
            if self.target:
                ret |= dict(target=self.target.to_dict())
            return ret


class Query:
    def __init__(self, node: Node, page: int, limit: int, order_by: str, descending: bool):
        self.node = node
        self.page = page
        self.limit = limit
        self.order_by = order_by
        self.descending = descending

    def to_dict(self):
        ret = dict()
        if self.node:
            ret |= dict(node=self.node.to_dict())
        if self.page:
            ret |= dict(page=self.page)
        if self.limit:
            ret |= dict(limit=self.limit)
        if self.order_by:
            ret |= dict(orderBy=self.order_by)
        if self.descending:
            ret |= dict(descending=self.descending)
        return ret


class Search:

    def __init__(self, api):
        self.api = api

    def count(self, search_term) -> {}:
        return self.api.count(dict(key=search_term))

    def by_key_prefix(self, key_prefix, offset=None, pages=10000) -> tuple:
        print(f'by_key_prefix() pages = {pages}')
        return self.by_term(key_prefix, None, offset, pages)

    def by_exact_key(self, key, get_attributes=False) -> {}:
        hits, _ = self.by_term(key, exact=True)
        hit = hits[0] if hits else None
        if get_attributes and hit:
            attributes, _ = self.by_source(key, 'attribute')
            hit['attributes'] = attributes
        return hit

    def by_source(self, source, kind, offset=None, pages=10000) -> tuple:
        return self.by_term(f'source:{source}', kind, offset, pages)

    def by_status(self, status_prefix, kind, offset=None, pages=10000) -> tuple:
        return self.by_term(f'status:{status_prefix}', kind, offset, pages)

    def by_name(self, name_prefix, kind, offset=None, pages=10000) -> tuple:
        return self.by_term(f'name:{name_prefix}', kind, offset, pages)

    def by_ip(self, ip_prefix, kind, offset=None, pages=10000) -> tuple:
        return self.by_term(f'ip:{ip_prefix}', kind, offset, pages)

    def by_dns(self, dns_prefix, kind, offset=None, pages=10000) -> tuple:
        return self.by_term(f'dns:{dns_prefix}', kind, offset, pages)

    def by_term(self, search_term, kind=None, offset=None, pages=10000, exact=False, descending=False,
                global_=False) -> tuple:
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

        # extract all the different types of entities in the search results into a
        # flattened list of `hits`
        # # REMOVE
        # print(f'by_term() pages = {pages}')
        results = self.api.my(params, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset

    def by_query(self, query: Query, pages=10000):
        results = self.api.my_by_query(query, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset


# {
#   "node": {
#     "relationships": [
#       {
#         "label": "HAS_VULNERABILITY",
#         "target": {
#           "labels": [
#             "Risk"
#           ],
#           "filters": [
#             {
#               "field": "key",
#               "operator": "=",
#               "value": "#risk#gladiator.systems#CVE-2018-1273"
#             }
#           ]
#         }
#       }
#     ]
#   }
# }


def flatten_results(results):
    if isinstance(results, list):
        return results
    flattened = []
    for key in results.keys():
        flattened.extend(flatten_results(results[key]))
    return flattened
