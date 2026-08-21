class Onboarding:

    def __init__(self, api):
        self.api = api

    def cloud_initialize(self, body):
        return self.api.post('cloud/initialize', body)

    def get_customer_domains(self):
        return self.api.get('customer/domains')

    def set_customer_domains(self, domains):
        return self.api.put('customer/domains', {'domains': domains})

    def verify_host_overrides(self, overrides):
        return self.api.post('setting/host-overrides/verify', overrides)

    def get_scim_settings(self):
        return self.api.get('scim/settings')

    def set_scim_settings(self, settings):
        return self.api.put('scim/settings', settings)
