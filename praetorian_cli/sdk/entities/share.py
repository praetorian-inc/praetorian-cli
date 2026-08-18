class Share:

    def __init__(self, api):
        self.api = api

    def create(self, body):
        return self.api.post('share', body)

    def list(self):
        return self.api.get('share')

    def delete(self, share_id):
        return self.api.delete('share', {'id': share_id}, {})

    def resolve(self, token):
        return self.api.get('share/' + token)
