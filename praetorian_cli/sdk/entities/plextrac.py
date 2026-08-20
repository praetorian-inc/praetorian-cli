class PlexTrac:

    def __init__(self, api):
        self.api = api

    def create_finding(self, risk_key, report_id):
        return self.api.post('plextrac/reporting', {
            'risk_key': risk_key,
            'report_id': report_id,
        })

    def get_reports(self, published=False):
        params = {}
        if published:
            params['published'] = 'true'
        return self.api.get('plextrac/reporting', params=params)

    def export(self, report_id):
        return self.api.get('plextrac/export', params={'reportId': str(report_id)})

    def connect_report(self, report_id):
        return self.api.put('plextrac/reports/connect', {'report_id': report_id})

    def disconnect_report(self, report_id):
        return self.api.delete('plextrac/reports/connect', {'report_id': report_id}, {})

    def update_definition(self, risk_key):
        return self.api.put('plextrac/definition', {'key': risk_key})
