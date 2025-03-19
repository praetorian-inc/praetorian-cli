from praetorian_cli.sdk.model.query import Query
from praetorian_cli.sdk.model.globals import EXACT_FLAG, DESCENDING_FLAG, GLOBAL_FLAG, Kind
class Search:

    def __init__(self, api):
        self.api = api

    def count(self, search_term) -> {}:
        return self.api.count(dict(key=search_term))

    def by_key_prefix(self, key_prefix, offset=None, pages=100000) -> tuple:
        return self.by_term(key_prefix, None, offset, pages)

    def by_exact_key(self, key, get_attributes=False) -> {}:
        hits, _ = self.by_term(key, exact=True)
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
