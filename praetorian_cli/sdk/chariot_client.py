import time


class ChariotClient:
    def __init__(self, keychain):
        self.keychain = keychain
        self.token = self.keychain.token()
        self.token_expiry = self.keychain.token_expiry

    def get_headers(self):
        if self.token_expiry < time.time():
            self.token = self.keychain.token()
            self.token_expiry = self.keychain.token_expiry
        return self.token
