import os
import shutil
import time

import pytest

from praetorian_cli.sdk.test import BaseTest
from praetorian_cli.sdk.test import utils


@pytest.mark.coherence
class TestFile(BaseTest):

    def setup_class(self):
        self.chariot, self.username = BaseTest.setup_chariot(self)
        self.file_name = "resources_asset_file.txt"
        self.upload_file = "resources/asset_file.txt"
        self.download_dir = "resources/downloads/"
        self.asset = f"contoso-{int(time.time())}.com"

        directory = os.path.dirname(self.upload_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(self.upload_file, 'w') as file:
            file.write(self.asset)

    def test_upload_file(self):
        self.chariot.upload(self.upload_file)

    def test_my_file(self):
        response = self.chariot.my(dict(key=f'#file#{self.upload_file}'))
        print(response)
        files = response['files']

        assert len(files) == 1
        assert files[0]['username'] == self.username
        assert files[0]['name'] == self.upload_file
        assert files[0]['key'] == f"#file#{self.upload_file}"

    def test_download_file(self):
        self.chariot.download(self.upload_file, self.download_dir)
        assert os.path.exists(self.download_dir) is True
        utils.assert_files_equal(self.upload_file, os.path.join(self.download_dir, self.file_name))

    def teardown_class(self):
        shutil.rmtree('resources')
