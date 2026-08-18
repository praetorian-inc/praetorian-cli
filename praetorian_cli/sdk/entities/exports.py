class Exports:

    def __init__(self, api):
        self.api = api

    def export_entity(self, entity_type, items=None, query=None, format='csv',
                      columns=None):
        body = {'label': entity_type, 'format': format}
        if items is not None:
            body['items'] = items
        if query is not None:
            body['query'] = query
        if columns:
            body['columns'] = columns
        return self.api.post('export/' + entity_type, body)

    def export_loa(self, body):
        return self.api.post('export/loa', body)

    def health_report(self):
        return self.api.post('report/health', {})
