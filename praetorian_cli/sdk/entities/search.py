from enum import Enum

from praetorian_cli.sdk.model.globals import Kind
from praetorian_cli.sdk.model.utils import get_type_from_key
EXACT_FLAG = {'exact': 'true'}
DESCENDING_FLAG = {'desc': 'true'}
GLOBAL_FLAG = {'global': 'true'}


class Filter:
    class Operator(Enum):
        EQUAL = '='
        CONTAINS = 'CONTAINS'
        LESS_THAN = '<'
        LARGER_THAN = '>'
        STARTS_WITH = 'STARTS WITH'
        ENDS_WITH = 'ENDS WITH'

    class Field(Enum): # Chariot.API.My depends upon these fields
        KEY = 'key'
        DNS = 'dns'
        NAME = 'name'
        STATUS = 'status'
        SOURCE = 'source'
        CREATED = 'created'

    def __init__(self, field: Field = None, operator: Operator = None, value: str = None, params: dict = None):
        if params:
            key = params.get('key', None)
            if key:
                if ':' in key:
                    field = Filter.Field(key.split(':')[0])
                    value = key.split(':')[1]
                else:
                    field = Filter.Field.KEY
                    value = key
                operator = Filter.Operator.STARTS_WITH
        self.field = field
        self.operator = operator
        self.value = value

    def to_dict(self) -> dict:
        if self.field == None or self.operator == None or self.value == None:
            return None
        return dict(field=self.field.value, operator=self.operator.value, value=self.value)

class Relationship:
    class Label(Enum):
        HAS_VULNERABILITY = 'HAS_VULNERABILITY'
        DISCOVERED = 'DISCOVERED'
        HAS_ATTRIBUTE = 'HAS_ATTRIBUTE'

    def __init__(self, label: Label, source: 'Node' = None, target: 'Node' = None):
        self.label = label
        self.source = source
        self.target = target

    def to_dict(self):
        ret = dict(label=self.label.value)
        if self.source:
            ret |= dict(source=self.source.to_dict())
        if self.target:
            ret |= dict(target=self.target.to_dict())
        return ret


class Node:
    class Label(Enum): # Chariot.API.My depends upon these labels
        ASSET = 'Asset'
        ATTRIBUTE = 'Attribute'
        RISK = 'Risk'
        PRESEED = 'Preseed'
        SEED = 'Seed'
        TTL = 'TTL'

    def __init__(self, labels: list[Label] = None, filters: list[Filter] = None,
                 relationships: list[Relationship] = None, params: dict = None):
        if params:
            filters = [Filter(params=params)]
            # During testing, it was found that having no labels returns no results.
            label = params.get('label', None)
            if label == None:
                for filter in filters:
                    label = get_type_from_key(filter.value)
            labels = Node.str_to_label(label)
            relationships = None # Not supported since params does not support relationships
        self.labels = labels
        self.filters = filters
        self.relationships = relationships

    def to_dict(self):
        ret = dict()
        if self.labels:
            ret |= dict(labels=[x.value for x in self.labels])
        if self.filters:
            ret |= dict(filters=[x.to_dict() for x in self.filters])
        if self.relationships:
            ret |= dict(relationships=[x.to_dict() for x in self.relationships])
        return ret      
    
    @staticmethod
    def str_to_label(str_of_label: str) -> list[Label]:
        if not str_of_label:
            return None
        for label in Node.Label:
            if label.name.lower() == str_of_label.lower():
                return [label]
        return None

class Query:
    def __init__(self, node: Node = None, page: int = 0, limit: int = 0, order_by: str = None,
                 descending: bool = False, params: dict = None):
        if params:
            node = Node(params=params)
            page = params.get('offset', page)
            limit = params.get('limit', limit)
            order_by = params.get('orderBy', order_by)
            descending = params.get('descending', descending)
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

    def by_key_prefix(self, key_prefix, offset=None, pages=100000) -> tuple:
        return self.by_term(key_prefix, None, offset, pages)

    def by_exact_key(self, key, get_attributes=False) -> {}:
        hits, _ = self.by_term(key, pages=1, exact=True)
        hit = hits[0] if hits else None
        if get_attributes and hit:
            attributes, _ = self.by_source(key, Kind.ATTRIBUTE.value)
            hit['attributes'] = attributes
        return hit

    def by_source(self, source, kind, offset=None, pages=100000) -> tuple:
        return self.by_term(f'source:{source}', kind, offset, pages)

    def by_status(self, status_prefix, kind, offset=None, pages=100000) -> tuple:
        return self.by_term(f'status:{status_prefix}', kind, offset, pages)

    def by_name(self, name_prefix, kind, offset=None, pages=100000) -> tuple:
        return self.by_term(f'name:{name_prefix}', kind, offset, pages)

    def by_dns(self, dns_prefix, kind, offset=None, pages=100000) -> tuple:
        return self.by_term(f'dns:{dns_prefix}', kind, offset, pages)

    def by_term(self, search_term, kind=None, offset=None, pages=100000, exact=False, descending=False,
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

        results = self.api.my(params, pages)

        if 'offset' in results:
            offset = results['offset']
            del results['offset']
        else:
            offset = None

        return flatten_results(results), offset

    def by_query(self, query: Query, pages=100000) -> tuple:
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


# helpers for building graph queries
ASSET_NODE = [Node.Label.ASSET]
RISK_NODE = [Node.Label.RISK]
ATTRIBUTE_NODE = [Node.Label.ATTRIBUTE]


def key_equals(key: str):
    return [Filter(Filter.Field.KEY, Filter.Operator.EQUAL, key)]


def risk_of_key(key: str):
    return Node(RISK_NODE, filters=key_equals(key))


def asset_of_key(key: str):
    return Node(ASSET_NODE, filters=key_equals(key))
