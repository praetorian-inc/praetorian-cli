from enum import Enum

from praetorian_cli.sdk.model.utils import get_type_from_key
from praetorian_cli.sdk.model.globals import GLOBAL_FLAG, Kind

class Filter:
    class Operator(Enum):
        EQUAL = '='
        CONTAINS = 'CONTAINS'
        LESS_THAN = '<'
        LARGER_THAN = '>'
        STARTS_WITH = 'STARTS WITH'
        ENDS_WITH = 'ENDS WITH'

    class Field(Enum): 
        KEY = 'key'
        DNS = 'dns'
        NAME = 'name'
        STATUS = 'status'
        SOURCE = 'source'
        CREATED = 'created'

    def __init__(self, field: Field, operator: Operator, value: str):
        self.field = field
        self.operator = operator
        self.value = value

    def to_dict(self) -> dict:
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
    class Label(Enum):
        ASSET = 'Asset'
        ATTRIBUTE = 'Attribute'
        RISK = 'Risk'
        PRESEED = 'Preseed'
        SEED = 'Seed'
        TTL = 'TTL'

    def __init__(self, labels: list[Label] = None, filters: list[Filter] = None,
                 relationships: list[Relationship] = None):
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

class Query:
    def __init__(self, node: Node = None, page: int = 0, limit: int = 0, order_by: str = None,
                 descending: bool = False, global_: bool = False):
        self.node = node
        self.page = page
        self.limit = limit
        self.order_by = order_by
        self.descending = descending
        self.global_ = global_

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
    
    def get_params(self):
        ret = dict()
        if self.global_:
            ret |= GLOBAL_FLAG
        return ret
    
class SimpleQueryBuilder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.labels = []
        self.filters = []
        self.relationships = []
        self.page = 0
        self.limit = 0
        self.order_by = None
        self.descending = False
        self.global_ = False

    def add_filter(self, field: Filter.Field, operator: Filter.Operator, value: str) -> 'SimpleQueryBuilder':
        self.filters.append(Filter(field, operator, value))
        return self

    def add_relationship(self, label: Relationship.Label, source: Node = None, target: Node = None) -> 'SimpleQueryBuilder':
        self.relationships.append(Relationship(label, source, target))
        return self

    def add_node_label(self, label: Node.Label) -> 'SimpleQueryBuilder':
        self.labels.append(label)
        return self
    
    def add_node_label_list(self, labels: list[Node.Label]) -> 'SimpleQueryBuilder':
        self.labels.extend(labels)
        return self

    def set_pagination(self, page: int, limit: int) -> 'SimpleQueryBuilder':
        self.page = page
        self.limit = limit
        return self

    def set_order(self, order_by: str, descending: bool = False) -> 'SimpleQueryBuilder':
        self.order_by = order_by
        self.descending = descending
        return self

    def set_global(self, global_: bool) -> 'SimpleQueryBuilder':
        self.global_ = global_
        return self

    def build(self) -> Query:
        node = Node(
            labels=self.labels if self.labels else None,
            filters=self.filters if self.filters else None,
            relationships=self.relationships if self.relationships else None
        )
        return Query(
            node=node,
            page=self.page,
            limit=self.limit,
            order_by=self.order_by,
            descending=self.descending,
            global_=self.global_
        )

class QueryBuilderDirector:

    def from_params(self, params: dict):
        self.builder = SimpleQueryBuilder()
        self.params = params

        self._params_filter()
        self._params_node_label()
        self._params_query()

        return self.builder.build()
        
    def _params_filter(self):
        key = self.params.get('key', None)
        if key:
            if ':' in key:
                field = Filter.Field(key.split(':')[0])
                value = key.split(':')[1]
            else:
                field = Filter.Field.KEY
                value = key
            
            if self.params.get('exact', False):
                operator = Filter.Operator.EQUAL
            else:
                operator = Filter.Operator.STARTS_WITH
            self.builder.add_filter(field=field, operator=operator, value=value)
    
    def _params_node_label(self):
        label = self.params.get('label', None)
        if label == None:
            for filter in self.builder.filters:
                label = get_type_from_key(filter.value)
        label = KIND_TO_LABEL.get(label, None)
        if label:
            self.builder.add_node_label(label=label)
    
    def _params_query(self):
        page = int(self.params.get('offset', 0))
        limit = int(self.params.get('limit', 0))
        global_ = bool(self.params.get('global', False))
        self.builder.set_pagination(page=page, limit=limit)
        self.builder.set_global(global_=global_)



# helpers for building graph queries
ASSET_NODE = [Node.Label.ASSET]
RISK_NODE = [Node.Label.RISK]
ATTRIBUTE_NODE = [Node.Label.ATTRIBUTE]

KIND_TO_LABEL = {
    Kind.ASSET.value: Node.Label.ASSET,
    Kind.RISK.value: Node.Label.RISK,
    Kind.ATTRIBUTE.value: Node.Label.ATTRIBUTE,
    Kind.SEED.value: Node.Label.SEED,
    Kind.PRESEED.value: Node.Label.PRESEED,
}


def key_equals(key: str):
    return [Filter(Filter.Field.KEY, Filter.Operator.EQUAL, key)]

def risk_of_key(key: str):
    return Node(RISK_NODE, filters=key_equals(key))

def asset_of_key(key: str):
    return Node(ASSET_NODE, filters=key_equals(key))

def isGraphType(key: str):
    if key:
        prefix_list = []
        prefix_list.extend([prefix.value.lower() for prefix in Filter.Field])
        prefix_list.extend([label.value.lower() for label in Node.Label])
        key = key.removeprefix('#')
        if any([key.startswith(prefix) for prefix in prefix_list]):
            return True
    return False