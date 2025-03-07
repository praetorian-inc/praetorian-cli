import os


class Files:
    """ The methods in this class are to be assessed from sdk.files, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, local_filepath, chariot_filepath=None):
        """ upload a file """
        return self.api.upload(local_filepath, chariot_filepath)

    def save(self, chariot_filepath, download_directory=os.getcwd()):
        """ download a file """
        content = self.get(chariot_filepath)

        local_filename = self.sanitize_filename(chariot_filepath)
        directory = os.path.expanduser(download_directory)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        download_path = os.path.join(directory, local_filename)
        with open(download_path, 'wb') as file:
            file.write(content)

        return download_path

    def get(self, chariot_filepath) -> bytes:
        """ download a file in memory """
        self.raise_if_missing(chariot_filepath)
        return self.api.download(chariot_filepath)

    def get_utf8(self, chariot_filepath) -> str:
        return self.get(chariot_filepath).decode('utf-8')

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List the files, optionally prefix-filtered by portion of the key after
            '#file#'. File keys read '#file#{filepath}' """
        return self.api.search.by_key_prefix(f'#file#{prefix_filter}', offset, pages)

    def delete(self, chariot_filepath):
        self.raise_if_missing(chariot_filepath)
        return self.api.delete('file', params=dict(name=chariot_filepath), body={})

    def sanitize_filename(self, filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def raise_if_missing(self, chariot_filepath):
        file = self.api.search.by_exact_key(f'#file#{chariot_filepath}')
        if not file:
            raise Exception(f'File {chariot_filepath} not found.')
