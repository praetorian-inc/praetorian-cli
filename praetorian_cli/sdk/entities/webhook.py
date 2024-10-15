from base64 import b64encode
from uuid import uuid4


class Webhook:
    """ The methods in this class are to be assessed from sdk.webhook, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def upsert(self):
        pin = str(uuid4())
        self.api.link_account('hook', pin)
        return self.webhook_url(pin)

    def get_url(self):
        hook = self.get_record()
        return self.webhook_url(hook['value']) if hook else None

    def get_record(self):
        integrations, offset = self.api.integrations.list()
        for i in integrations:
            if i['member'] == 'hook':
                return i
        return None

    def delete(self):
        hook = self.get_record()
        if hook:
            self.api.delete('account/hook', hook['key'], dict(member='hook', value=hook['value']))
            return hook
        else:
            return None

    def webhook_url(self, pin):
        username = b64encode(self.api.keychain.username().encode('utf8'))
        return f'{self.api.keychain.base_url()}/hook/{username.decode("utf8").rstrip("=")}/{pin}'
