import json
import os
from base64 import b64encode
from uuid import uuid4

import requests

from praetorian_cli.sdk.keychain import verify_credentials, Keychain


class Chariot:

    def __init__(self, keychain: Keychain):
        self.keychain = keychain

    @verify_credentials
    def my(self, params: dict, pages=1) -> {}:
        my_resp = dict()
        for _ in range(pages):
            resp = requests.get(f"{self.keychain.api}/my",
                                params=params, headers=self.keychain.headers)
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

    @verify_credentials
    def count(self, params: dict) -> {}:
        resp = requests.get(f"{self.keychain.api}/my/count",
                            params=params, headers=self.keychain.headers)
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def add(self, type, payload: dict) -> {}:
        resp = requests.post(f"{self.keychain.api}/{type}",
                             json=payload, headers=self.keychain.headers)
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def delete(self, type, key: str) -> {}:
        resp = requests.delete(f"{self.keychain.api}/{type}", json={'key': key},
                               headers=self.keychain.headers)
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def update(self, resource: str, data: dict) -> {}:
        resp = requests.put(f"{self.keychain.api}/{resource}",
                            json=data, headers=self.keychain.headers)
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def report(self, name: str) -> {}:
        resp = requests.get(f"{self.keychain.api}/report/risk",
                            {'name': name}, headers=self.keychain.headers)
        process_failure(resp)
        return resp.text

    @verify_credentials
    def link_account(self, username: str, config: dict, id: str = ""):
        resp = requests.post(f"{self.keychain.api}/account/{username}", json={'config': config, 'value': id},
                             headers=self.keychain.headers)
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def unlink(self, username: str, id: str = ""):
        resp = requests.delete(f"{self.keychain.api}/account/{username}", headers=self.keychain.headers,
                               json={'value': id})
        process_failure(resp)
        return resp.json()

    @verify_credentials
    def upload(self, name: str, upload_path: str = ""):
        path = upload_path if upload_path else name
        with open(name, 'rb') as content:
            self._upload(path, content)

    @verify_credentials
    def _upload(self, name: str, content: str):
        # It is a two-step upload. The PUT request to the /file endpoint is to get a presigned URL for S3.
        # There is no data transfer.
        presigned_url = requests.put(f"{self.keychain.api}/file", params={"name": name},
                                     headers=self.keychain.headers)
        process_failure(presigned_url)
        requests.put(presigned_url.json()["url"], data=content)

    def sanitize_filename(self, filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    @verify_credentials
    def download(self, name: str, download_path: str) -> bool:
        resp = requests.get(f"{self.keychain.api}/file", params={"name": name}, allow_redirects=True,
                            headers=self.keychain.headers)
        process_failure(resp)

        name = self.sanitize_filename(name)
        directory = os.path.expanduser(download_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        download_path = os.path.join(directory, name)

        with open(download_path, 'wb') as file:
            file.write(resp.content)

        return download_path

    @verify_credentials
    def add_webhook(self):
        pin = str(uuid4())
        self.link_account(username="hook", config={'pin': pin})
        username = b64encode(self.keychain.username.encode('utf8'))
        encoded_string = username.decode('utf8')
        encoded_username = encoded_string.rstrip('=')
        return f'{self.keychain.api}/hook/{encoded_username}/{pin}'

    @verify_credentials
    def purge(self):
        requests.delete(f"{self.keychain.api}/account/purge", headers=self.keychain.headers)

    def get_risk_details(self, key: str):
        resp = self.my(dict(key=key))['risks'][0]
        poe = f"{resp['dns']}/{resp['name']}"
        definition = f"definitions/{resp['name']}"
        poe_content = ""
        risk_definition = ""
        try:
            for item in [poe, definition]:
                downloaded_path = self.download(item, "")
                with open(downloaded_path, 'r') as file:
                    if item == poe:
                        poe_content = file.read()
                    else:
                        risk_definition = file.read()
                os.remove(downloaded_path)
        except Exception as e:
            print(f"Failed to download file: {e}. Skipping.")
        try:
            poe_json = json.loads(poe_content) if poe_content else {}
        except json.JSONDecodeError:
            poe_json = {}
        resp.update({
            "url": poe_json.get("url", ""),
            "ip": poe_json.get("ip", ""),
            "port": poe_json.get("port", ""),
            "proof of exploit": b64encode(poe_content.encode('utf-8')).decode('utf-8') if poe_content else "",
            "description": risk_definition
        })
        return resp


def process_failure(response):
    if not response.ok:
        message = f'[{response.status_code}] Request failed' + (f'\nError: {response.text}' if response.text else '')
        raise Exception(message)
