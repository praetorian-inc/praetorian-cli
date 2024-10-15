import os


class Files:
    """ The methods in this class are to be assessed from sdk.files, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, local_filepath, chariot_filepath=None):
        """ upload a file """
        return self.api.upload(local_filepath, chariot_filepath)

    def get(self, chariot_filepath, download_directory=os.getcwd()):
        """ download a file """
        return self.api.download(chariot_filepath, download_directory)

    def list(self, prefix_filter='', offset=None, pages=1000):
        """ List the files, optionally prefix-filtered by portion of the key after
            '#file#'. File keys read '#file#{filepath}' """
        return self.api.search.by_key_prefix(f'#file#{prefix_filter}', offset, pages)
