import json
import time

import requests

from praetorian_cli.sdk.chariot import process_failure


class ChariotClient:
    def __init__(self, keychain):
        self.keychain = keychain
        self.token = self.keychain.token()
        self.token_expiry = self.keychain.token_expiry

    def get_headers(self):
        if self.token_expiry < time.time():
            self.token = self.keychain.token()
            self.token_expiry = self.keychain.token_expiry
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def my(self, params: dict, pages=1) -> {}:
        my_resp = dict()
        for _ in range(pages):
            resp = requests.get(f"{self.keychain.api}/my",
                                params=params, headers=self.get_headers())
            process_failure(resp)
            resp = resp.json()
            for key, value in resp.items():
                if key in my_resp and isinstance(value, list):
                    my_resp[key].extend(value)
                else:
                    my_resp[key] = value
            if 'offset' in resp:
                params['offset'] = json.dumps(resp['offset'])
            else:
                my_resp.pop('offset', None)
                break
        return my_resp
