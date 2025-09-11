import os


class Definitions:
    """ The methods in this class are to be assessed from sdk.definitions, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        """
        Initialize the Definitions entity manager.

        :param api: The API client instance for making requests
        :type api: object
        """
        self.api = api

    def add(self, local_filepath, definition_name=None):
        """
        Upload a risk definition file to the definitions folder.

        :param local_filepath: The local file path of the definition file to upload (must be in Markdown format)
        :type local_filepath: str
        :param definition_name: The name to use for the definition (defaults to the basename of the local file)
        :type definition_name: str or None
        :return: The result from the file upload operation
        :rtype: dict
        """
        if not definition_name:
            definition_name = os.path.basename(local_filepath)
        return self.api.files.add(local_filepath, f'definitions/{definition_name}')

    def get(self, definition_name, download_directory=os.getcwd(), global_=False):
        """
        Download a risk definition file from the definitions folder.

        :param definition_name: The name of the definition file to download
        :type definition_name: str
        :param download_directory: The directory to save the downloaded file (defaults to current working directory)
        :type download_directory: str
        :param global_: If True, fetch from global definitions instead of user-specific
        :type global_: bool
        :return: The local file path where the definition was saved
        :rtype: str
        """
        try:
            content = self.api.files.get_utf8(f'definitions/{definition_name}', _global=global_)
        except Exception as e:
            if global_:
                raise Exception(f'Global definition {definition_name} not found or inaccessible.')
            else:
                raise
        download_path = os.path.join(download_directory, definition_name)
        with open(download_path, 'w') as file:
            file.write(content)
        return download_path


    def list(self, name_filter='', offset=None, pages=100000) -> tuple:
        """
        List the definition names, optionally prefix-filtered by a definition name.

        :param name_filter: The prefix filter to apply to definition names (empty string returns all definitions)
        :type name_filter: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of definition names, next page offset)
        :rtype: tuple
        """
        definitions, next_offset = self.api.search.by_key_prefix(f'#file#definitions/{name_filter}', offset, pages)
        names = [d['name'][12:] for d in definitions]
        return names, next_offset
