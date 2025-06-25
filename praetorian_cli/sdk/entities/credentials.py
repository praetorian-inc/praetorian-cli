import os
from pathlib import Path
from praetorian_cli.sdk.model.globals import Kind


class Credentials:
    """ The methods in this class are to be accessed from sdk.credentials, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self, offset=None, pages=100000):
        """ List credentials

        Arguments:
        offset: str
            The offset of the page you want to retrieve results. If this is not supplied,
            this function retrieves from the first page.
        pages: int
            The number of pages of results to retrieve.
        """
        return self.api.search.by_key_prefix('#credential', offset=offset, pages=pages)

    def get(self, credential_id, category, type, format, **parameters):
        """ Get a specific credential

        Arguments:
        credential_id: str
            The ID of the credential to retrieve
        type: str
            The type of credential (e.g., 'aws', 'gcp', 'azure', 'static', 'ssh_key', 'json')
        format: str
            The format of the credential response
        **parameters: dict
            Additional parameters required for the credential request
        """
        request = {
            'CredentialID': credential_id,
            'Category': category,
            'Type': type,
            'Format': format,
            'Parameters': parameters
        }
        response = self.api.post('broker', request)
        return self._process_credential_output(response, format)

    def _process_credential_output(self, response, format):
        """ Process credential response based on type
        
        Arguments:
        response: dict
            The raw credential response from the broker API
        format: str or list
            The format(s) requested for the credential
        """
        import json
        
        primary_format = format[0] if isinstance(format, list) else format
        
        if primary_format == 'token' or 'CredentialValue' in response:
            if response.get('CredentialValue'):
                return response
        
        if 'CredentialValueFiles' in response and response['CredentialValueFiles']:
            written_files = []
            for cred_file in response['CredentialValueFiles']:
                file_path = cred_file['CredentialFileLocation']
                
                if file_path.startswith('~/'):
                    file_path = os.path.expanduser(file_path)
                
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                
                content = cred_file['CredentialFileContent']
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
        
        if 'CredentialValueEnv' in response and response['CredentialValueEnv']:
            env_vars = []
            for key, value in response['CredentialValueEnv'].items():
                env_vars.append(f"{key}={value}")
            
            return {
                'message': f'Environment variables for sourcing:',
                'env_vars': env_vars,
                'source_format': '\n'.join(env_vars),
                'credential_response': response
            }
        
        return response

    def format_output(self, result):
        """ Format credential output based on type and return string to print """
        import json
        
        if isinstance(result, dict) and 'files' in result:
            output_lines = [result['message']]
            for file_path in result['files']:
                output_lines.append(f"  {file_path}")
            return '\n'.join(output_lines)
        elif isinstance(result, dict) and 'env_vars' in result:
            return f"{result['message']}\n{result['source_format']}"
        else:
            return json.dumps(result, indent=2)
