class Constantine:

    def __init__(self, api):
        self.api = api

    def exploit(self, risk_keys):
        return self.api.post('constantine/exploit', {'risk_keys': risk_keys})

    def patch(self, risk_keys):
        return self.api.post('constantine/patch', {'risk_keys': risk_keys})

    def patch_and_pr(self, risk_key):
        return self.api.post('constantine/patch-and-pr', {'risk_key': risk_key})

    def validate(self, risk_keys):
        return self.api.post('constantine/validate', {'risk_keys': risk_keys})

    def manifest(self):
        return self.api.get('constantine/manifest')
