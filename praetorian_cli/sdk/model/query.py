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

def convert_params_to_query(params: dict):
    key = params.get('key', None)
    if key == None:
        return None, False
    
    if not isGraphType(key):
        return None, False
    
    # We set the filter based on if key in field:value format (source:key)
    # or just a key
    if ':' in key:
        field = Filter.Field(key.split(':')[0])
        value = key.split(':')[1]
    else:
        field = Filter.Field.KEY
        value = key
    
    if params.get('exact', False):
        operator = Filter.Operator.EQUAL
    else:
        operator = Filter.Operator.STARTS_WITH
    
    filter = Filter(field, operator, value)

    # Label is set if we are using a key:value format 
    label = params.get('label', get_type_from_key(filter.value))
    label = KIND_TO_LABEL.get(label, None)
    if label == None:
        return None, False
    
    node = Node(labels=[label], filters=[filter])

    page = int(params.get('offset', 0))
    limit = int(params.get('limit', 5000))
    global_ = bool(params.get('global', False))

    return Query(node=node, page=page, limit=limit, global_=global_), True
    