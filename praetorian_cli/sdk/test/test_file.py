import os

import pytest

from praetorian_cli.sdk.test.utils import epoch_micro, random_ip, setup_chariot


@pytest.mark.coherence
class TestFile:

    def setup_class(self):
        self.sdk = setup_chariot()
        micro = epoch_micro()
        self.chariot_filepath = f'home/test-file-{micro}.txt'
        self.encrypted_chariot_filepath = f'_encrypted/test-file-{micro}.txt'
        self.sanitized_filepath = f'home_test-file-{micro}.txt'
        self.bogus_filepath = f'bogus-filepath-{micro}.txt'
        self.local_filepath = f'./test-file-{micro}.txt'
        self.content = random_ip()
        with open(self.local_filepath, 'w') as file:
            file.write(self.content)

    def test_sanitized_filepath(self):
        assert self.sdk.files.sanitize_filename(self.chariot_filepath) == self.sanitized_filepath

    def test_add_file(self):
        self.sdk.files.add(self.local_filepath, self.chariot_filepath)
        files, offset = self.sdk.files.list(self.chariot_filepath)
        assert files[0]['name'] == self.chariot_filepath

    def test_save_file(self):
        self.sdk.files.save(self.chariot_filepath, os.getcwd())
        with open(self.sanitized_filepath, 'r') as f:
            assert f.read() == self.content

    def test_get_file(self):
        content = self.sdk.files.get_utf8(self.chariot_filepath)
        assert content == self.content

    def test_get_non_existent_file(self):
        with pytest.raises(Exception) as ex_info:
            self.sdk.files.get(self.bogus_filepath)
        assert str(ex_info.value) == f'File {self.bogus_filepath} not found.'

    def test_delete_non_existent_file(self):
        with pytest.raises(Exception) as ex_info:
            self.sdk.files.delete(self.bogus_filepath)
        assert str(ex_info.value) == f'File {self.bogus_filepath} not found.'

    def test_delete_file(self):
        self.sdk.files.delete(self.chariot_filepath)
        with pytest.raises(Exception) as ex_info:
            self.sdk.files.get(self.chariot_filepath)
        assert str(ex_info.value) == f'File {self.chariot_filepath} not found.'

    def test_add_encrypted_file(self):
        self.sdk.files.add(self.local_filepath, self.encrypted_chariot_filepath)
        files, offset = self.sdk.files.list(self.encrypted_chariot_filepath)
        assert files[0]['name'] == self.encrypted_chariot_filepath

    def test_get_encrypted_file(self):
        content = self.sdk.files.get_utf8(self.encrypted_chariot_filepath)
        assert content == self.content

    def test_delete_encrypted_file(self):
        self.sdk.files.delete(self.encrypted_chariot_filepath)
        with pytest.raises(Exception) as ex_info:
            self.sdk.files.get(self.encrypted_chariot_filepath)
        assert str(ex_info.value) == f'File {self.encrypted_chariot_filepath} not found.'

    def teardown_class(self):
        os.remove(self.local_filepath)
        os.remove(self.sanitized_filepath)
