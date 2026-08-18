class Multipart:

    def __init__(self, api):
        self.api = api

    def create(self, name, praetorian=False, ttl=None):
        params = {'name': name}
        if praetorian:
            params['praetorian'] = 'true'
        if ttl is not None:
            params['ttl'] = str(ttl)
        return self.api.post('file/multipart/create', {}, params=params)

    def get_part_url(self, name, upload_id, part_number, praetorian=False):
        params = {
            'name': name,
            'uploadId': upload_id,
            'partNumber': str(part_number),
        }
        if praetorian:
            params['praetorian'] = 'true'
        return self.api.post('file/multipart/part', {}, params=params)

    def complete(self, name, upload_id, parts, praetorian=False):
        params = {}
        if praetorian:
            params['praetorian'] = 'true'
        return self.api.post('file/multipart/complete', {
            'name': name,
            'uploadId': upload_id,
            'parts': parts,
        }, params=params)

    def abort(self, name, upload_id, praetorian=False):
        params = {}
        if praetorian:
            params['praetorian'] = 'true'
        return self.api.post('file/multipart/abort', {
            'name': name,
            'uploadId': upload_id,
        }, params=params)
