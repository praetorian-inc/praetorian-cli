class Knossos:
    def __init__(self, api):
        self.api = api

    def profile(self):
        return self.api.get('knossos/profile')

    def profile_infer(self, body):
        return self.api.post('knossos/profile/infer', body)

    def profile_versions(self):
        return self.api.get('knossos/profile/versions')

    def generate(self, body):
        return self.api.post('knossos/environment/generate', body)

    def environments(self):
        return self.api.get('knossos/environments')

    def environment(self, env_id):
        return self.api.get(f'knossos/environment/{env_id}')

    def delete_environment(self, env_id):
        return self.api.delete(f'knossos/environment/{env_id}', {}, {})

    def emit(self, env_id):
        return self.api.post(f'knossos/environment/{env_id}/emit', {})

    def cost(self, env_id, refresh=False):
        if refresh:
            return self.api.post(f'knossos/environment/{env_id}/cost', {})
        return self.api.get(f'knossos/environment/{env_id}/cost')

    def validate(self, env_id):
        return self.api.post(f'knossos/environment/{env_id}/validate', {})

    def deploy(self, env_id):
        return self.api.post(f'knossos/environment/{env_id}/deploy', {})

    def status(self, env_id):
        return self.api.get(f'knossos/environment/{env_id}/status')

    def events(self, env_id, since=None, until=None, lure_id=None,
               event_type=None, limit=None, offset=None):
        params = {}
        if since:
            params['since'] = since
        if until:
            params['until'] = until
        if lure_id:
            params['lureId'] = lure_id
        if event_type:
            params['eventType'] = event_type
        if limit:
            params['limit'] = str(limit)
        if offset:
            params['offset'] = str(offset)
        return self.api.get(f'knossos/environment/{env_id}/events', params=params)
