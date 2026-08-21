class HackerOne:

    def __init__(self, api):
        self.api = api

    def sync_scope(self):
        return self.api.post('hackerone/sync-scope', {})

    def programs(self):
        return self.api.get('hackerone/programs')

    def program_scopes(self, handle):
        return self.api.get('hackerone/programs/' + handle + '/scopes')

    def program_weaknesses(self, handle):
        return self.api.get('hackerone/programs/' + handle + '/weaknesses')

    def comment(self, report_id, message, internal=False, source='hacker-api',
                attachment_s3_keys=None):
        body = {
            'report_id': report_id,
            'message': message,
            'internal': internal,
            'source': source,
        }
        if attachment_s3_keys:
            body['attachment_s3_keys'] = attachment_s3_keys
        return self.api.post('hackerone/comment', body)

    def activities(self, report_id, source='hacker-api'):
        return self.api.get('hackerone/activities', params={
            'reportId': report_id,
            'source': source,
        })

    def severity(self, report_id, rating, source='org-api'):
        return self.api.post('hackerone/severity', {
            'report_id': report_id,
            'rating': rating,
            'source': source,
        })

    def bounty_catalog(self):
        return self.api.get('bounty-catalog')
