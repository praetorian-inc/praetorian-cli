import os


class Definitions:
    """ The methods in this class are to be assessed from sdk.definitions, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, local_filepath, definition_name=None):
        """ upload a risk definition file """
        if not definition_name:
            definition_name = os.path.basename(local_filepath)
        return self.api.files.add(local_filepath, f'definitions/{definition_name}')

    def get(self, definition_name, download_directory=os.getcwd()):
        """ download a risk definition file """
        content = self.api.download(f'definitions/{definition_name}', '')
        download_path = os.path.join(download_directory, definition_name)
        with open(download_path, 'w') as file:
            file.write(content)
        return download_path

    def list(self, name_filter='', offset=None, pages=10000):
        """ List the definition names, optionally prefix-filtered by a definition name """
        definitions, next_offset = self.api.search.by_key_prefix(f'#file#definitions/{name_filter}', offset, pages)
        names = [d['name'][12:] for d in definitions]
        return names, next_offset
