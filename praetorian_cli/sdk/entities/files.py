import os


class Files:
    """ The methods in this class are to be assessed from sdk.files, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, local_filepath, chariot_filepath=None):
        """
        Upload a file to Chariot storage.

        :param local_filepath: Path to the local file to upload
        :type local_filepath: str
        :param chariot_filepath: Optional destination path in Chariot storage. If None, uses the local filename
        :type chariot_filepath: str or None
        :return: The uploaded file entity
        :rtype: dict
        """
        return self.api.upload(local_filepath, chariot_filepath)

    def save(self, chariot_filepath, download_directory=os.getcwd()):
        """
        Download a file from Chariot storage to the local filesystem.

        :param chariot_filepath: Path of the file in Chariot storage to download
        :type chariot_filepath: str
        :param download_directory: Local directory to save the file (defaults to current working directory)
        :type download_directory: str
        :return: The local path where the file was saved
        :rtype: str
        :raises Exception: If the file does not exist in Chariot storage
        """
        content = self.get(chariot_filepath)

        local_filename = self.sanitize_filename(chariot_filepath)
        directory = os.path.expanduser(download_directory)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        download_path = os.path.join(directory, local_filename)
        with open(download_path, 'wb') as file:
            file.write(content)

        return download_path

    def get(self, chariot_filepath, _global=False) -> bytes:
        """
        Download a file from Chariot storage into memory as bytes.

        :param chariot_filepath: Path of the file in Chariot storage to download
        :type chariot_filepath: str
        :param _global: If True, fetch from global storage instead of user-specific
        :type _global: bool
        :return: The file content as bytes
        :rtype: bytes
        :raises Exception: If the file does not exist in Chariot storage
        """
        if not _global:
            self.raise_if_missing(chariot_filepath)
        return self.api.download(chariot_filepath, global_=_global)

    def get_utf8(self, chariot_filepath, _global=False) -> str:
        """
        Download a file from Chariot storage into memory as a UTF-8 string.

        :param chariot_filepath: Path of the file in Chariot storage to download
        :type chariot_filepath: str
        :param _global: If True, fetch from global storage instead of user-specific
        :type _global: bool
        :return: The file content as a UTF-8 decoded string
        :rtype: str
        :raises Exception: If the file does not exist in Chariot storage
        """
        return self.get(chariot_filepath, _global=_global).decode('utf-8')

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List files in Chariot storage, optionally filtered by filepath prefix.

        File keys internally use the format '#file#{filepath}', but this method
        filters by the filepath portion after '#file#'.

        :param prefix_filter: Filter results by filepath prefix (e.g., 'home/', 'imports/')
        :type prefix_filter: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching file entities, next page offset)
        :rtype: tuple
        """
        return self.api.search.by_key_prefix(f'#file#{prefix_filter}', offset, pages)

    def delete(self, chariot_filepath):
        """
        Delete a file from Chariot storage.

        :param chariot_filepath: Path of the file in Chariot storage to delete
        :type chariot_filepath: str
        :return: The deleted file entity
        :rtype: dict
        :raises Exception: If the file does not exist in Chariot storage
        """
        self.raise_if_missing(chariot_filepath)
        return self.api.delete('file', params=dict(name=chariot_filepath), body={})

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for cross-platform filesystem compatibility.

        Replaces invalid filesystem characters (<>:"/\\|?*) with underscores
        to ensure the filename can be safely used on Windows, macOS, and Linux.

        :param filename: The filename to sanitize
        :type filename: str
        :return: The sanitized filename with invalid characters replaced by underscores
        :rtype: str
        """
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def raise_if_missing(self, chariot_filepath):
        """
        Check if a file exists in Chariot storage and raise an exception if not found.

        This is a utility method used internally by other file operations to validate
        file existence before performing operations like download or delete.

        :param chariot_filepath: Path of the file in Chariot storage to check
        :type chariot_filepath: str
        :return: None
        :rtype: None
        :raises Exception: If the file does not exist in Chariot storage with message 'File {chariot_filepath} not found.'
        """
        file = self.api.search.by_exact_key(f'#file#{chariot_filepath}')
        if not file:
            raise Exception(f'File {chariot_filepath} not found.')
