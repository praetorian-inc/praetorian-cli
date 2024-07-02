import time

import requests


def assert_files_equal(file1_path, file2_path):
    with open(file1_path, 'r') as file1:
        content1 = file1.read()

    with open(file2_path, 'r') as file2:
        content2 = file2.read()

    assert content1 == content2, f"Contents of the files {file1_path} and {file2_path} file are not equal"


def add_asset_via_webhook(webhook, asset_payload):
    webhook_post = requests.post(url=webhook, json=asset_payload)
    assert webhook_post.status_code == 200, "Webhook POST request failed"


class Utils:
    def __init__(self, chariot):
        self.chariot = chariot

    def wait_for_key(self, key, timeout=60, interval=5):
        start_time = time.time()
        while time.time() - start_time < timeout:
            print(f"Trying to get response for my {key}")
            response = self.chariot.my(key)
            if response:
                return response
            time.sleep(interval)
