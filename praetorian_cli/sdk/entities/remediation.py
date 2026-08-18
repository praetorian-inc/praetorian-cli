class Remediation:

    def __init__(self, api):
        self.api = api

    def select_patch(self, risk_key, finding_id, option_id, strategy=None):
        body = {'risk_key': risk_key, 'finding_id': finding_id, 'option_id': option_id}
        if strategy:
            body['strategy'] = strategy
        return self.api.put('remediation', body)

    def clear_patch(self, risk_key, finding_id):
        return self.api.delete('remediation', {'risk_key': risk_key, 'finding_id': finding_id}, {})

    def create_pr(self, risk_key, finding_id):
        return self.api.post('remediation/pr', {'risk_key': risk_key, 'finding_id': finding_id})
