import os
from pathlib import Path


class Credentials:
    """ The methods in this class are to be accessed from sdk.credentials, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, resource_key, category, type, label, parameters):
        """
        Add a new credential to the credential broker.

        :param resource_key: The resource key for the credential (e.g., account key)
        :type resource_key: str
        :param category: The category of the credential ('integration', 'cloud', 'env-integration')
        :type category: str
        :param type: The type of credential ('aws', 'gcp', 'azure', 'static', 'ssh_key', 'json', 'active-directory', 'default')
        :type type: str
        :param label: A human-readable label for the credential
        :type label: str
        :param parameters: Additional parameters for the credential (e.g., username, password, domain)
        :type parameters: dict
        :return: The response from the broker API
        :rtype: dict
        """
        request = {
            'Operation': 'add',
            'ResourceKey': resource_key,
            'Category': category,
            'Type': type,
            'Parameters': parameters | {'label': label}
        }
        return self.api.post('broker', request)

    def list(self, offset=None, pages=100000):
        """
        List credentials available to the current principal.

        :param offset: The offset of the page you want to retrieve results. If not supplied, retrieves from first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of credential entities, next page offset)
        :rtype: tuple
        """
        return self.api.search.by_key_prefix('#credential', offset=offset, pages=pages)

    def get(self, credential_id, category, type, format, **parameters):
        """
        Get a specific credential using the credential broker.

        :param credential_id: The ID of the credential to retrieve
        :type credential_id: str
        :param category: The category of the credential ('integration', 'cloud', 'env-integration')
        :type category: str
        :param type: The type of credential ('aws', 'gcp', 'azure', 'static', 'ssh_key', 'json', 'default')
        :type type: str
        :param format: The format of the credential response ('token', 'file', 'env')
        :type format: str or list
        :param parameters: Additional parameters required for the credential request (e.g., region, role_arn)
        :type parameters: dict
        :return: The processed credential response based on the requested format
        :rtype: dict or str
        """
        request = {
            'Operation': 'get',
            'CredentialID': credential_id,
            'Category': category,
            'Type': type,
            'Format': format,
            'Parameters': parameters
        }
        response = self.api.post('broker', request)
        return self._process_credential_output(response, format)

    def _process_credential_output(self, response, format):
        """
        Process credential response based on the requested format.

        Handles different credential formats: 'token' returns raw response,
        'file' writes credential files to disk and returns file paths,
        'env' returns formatted environment variable export statements.

        :param response: The raw credential response from the broker API
        :type response: dict
        :param format: The format(s) requested for the credential ('token', 'file', 'env')
        :type format: str or list
        :return: Processed credential data - dict for token/file formats, str for env format
        :rtype: dict or str
        """
        primary_format = format[0] if isinstance(format, list) else format

        if primary_format == 'token':
            return response

        if primary_format == 'file':
            written_files = []
            for cred_file in response['credentialValueFile']:
                file_path = cred_file['credentialFileLocation']

                if file_path.startswith('~/'):
                    file_path = os.path.expanduser(file_path)

                Path(file_path).parent.mkdir(parents=True, exist_ok=True)

                content = cred_file['credentialFileContent']
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                elif not isinstance(content, str):
                    content = str(content)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.chmod(file_path, 0o600)

                written_files.append(file_path)

            return {
                'message': f'Wrote {len(written_files)} credential file(s)',
                'files': written_files,
                'credential_response': response
            }

        if primary_format == 'env':
            env_vars = []
            for key, value in response['credentialValueEnv'].items():
                env_vars.append(f"export {key}={value}")

            return '\n'.join(env_vars)

        return response

    def format_output(self, result):
        """
        Format credential output for display to the user.

        Handles different result types: file credential results show file paths,
        string results are returned as-is, other types are JSON formatted.

        :param result: The credential result to format (from get() method)
        :type result: dict or str or any
        :return: Formatted string ready for display to the user
        :rtype: str
        """
        import json

        if isinstance(result, dict) and 'files' in result:
            output_lines = [result['message']]
            for file_path in result['files']:
                output_lines.append(f"  {file_path}")
            return '\n'.join(output_lines)
        elif isinstance(result, str):
            return result
        else:
            return json.dumps(result, indent=2)
