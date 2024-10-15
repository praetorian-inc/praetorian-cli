class Search:

    def __init__(self, api):
        self.api = api

    def count(self, search_term) -> {}:
        return self.api.count(dict(key=search_term))

    def by_key_prefix(self, key_prefix, offset=None, pages=1000) -> tuple:
        return self.by_term(key_prefix, offset, pages)

    def by_exact_key(self, key, get_attributes=False) -> {}:
        hits, _ = self.by_term(key, exact=True)
        hit = hits[0] if hits else None
        if get_attributes and hit:
            attributes, _ = self.by_source(key)
            hit['attributes'] = attributes
        return hit

    def by_source(self, source, offset=None, pages=1000) -> tuple:
        return self.by_term(f'source:{source}', offset, pages)

    def by_status(self, status_prefix, offset=None, pages=1000) -> tuple:
        return self.by_term(f'status:{status_prefix}', offset, pages)

    def by_name(self, name_prefix, offset=None, pages=1000) -> tuple:
        return self.by_term(f'name:{name_prefix}', offset, pages)

    def by_ip(self, ip_prefix, offset=None, pages=1000) -> tuple:
        return self.by_term(f'ip:{ip_prefix}', offset, pages)

    def by_dns(self, dns_prefix, offset=None, pages=1000) -> tuple:
        return self.by_term(f'dns:{dns_prefix}', offset, pages)

    def by_term(self, search_term, offset=None, pages=1000, exact=False) -> tuple:
        params = dict(key=search_term)
        if offset:
            params = params | dict(offset=offset)
        if exact:
            params = params | dict(exact='true')

        # extract all the different types of entities in the search results into a
        # flattened list of `hits`
        results = self.api.my(params, pages)
        hits = []
        for key in results.keys():
            if key != 'offset':
                hits.extend(results[key])
        offset = results['offset'] if 'offset' in results else None
        return hits, offset
