import os

import pytest

from praetorian_cli.sdk.test.utils import epoch_micro, random_ip, setup_chariot


@pytest.mark.coherence
class TestFile:

    def setup_class(self):
        self.sdk = setup_chariot()
        micro = epoch_micro()
        self.chariot_filepath = f'home/test-file-{micro}.txt'
        self.sanitized_filepath = f'home_test-file-{micro}.txt'
        self.local_filepath = f'./test-file-{micro}.txt'
        self.content = random_ip()
        with open(self.local_filepath, 'w') as file:
            file.write(self.content)

    def test_add_file(self):
        self.sdk.files.add(self.local_filepath, self.chariot_filepath)
        files, offset = self.sdk.files.list(self.chariot_filepath)
        assert files[0]['name'] == self.chariot_filepath

    def test_get_file(self):
        self.sdk.files.get(self.chariot_filepath, os.getcwd())
        with open(self.sanitized_filepath, 'r') as f:
            assert f.read() == self.content

    def teardown_class(self):
        os.remove(self.local_filepath)
        os.remove(self.sanitized_filepath)
