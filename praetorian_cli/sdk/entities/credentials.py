import json
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

        :param resource_key: The resource key for the credential (e.g., account key, web-application key)
        :type resource_key: str
        :param category: The category of the credential ('integration', 'cloud', 'env-integration')
        :type category: str
        :param type: The type of credential ('aws', 'gcp', 'azure', 'static-token', 'ssh-key',
            'json-credential', 'active-directory', 'burp-authentication', 'web-auth', etc.)
        :type type: str
        :param label: A human-readable label for the credential
        :type label: str
        :param parameters: Additional parameters for the credential (e.g., username, password, domain,
            or for web-auth: method + headers dict)
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

    def add_active_directory(
        self,
        label,
        endpoint_ids,
        domain,
        auth_type,
        **material,
    ):
        """Create a v2 Active Directory credential for specific endpoints."""
        endpoint_ids = _required_strings(endpoint_ids, 'endpoint IDs')
        parameters = {
            'endpointIds': endpoint_ids,
            'domain': _required_string(domain, 'domain'),
            'authType': _required_string(auth_type, 'auth type'),
            **{
                key: value for key, value in material.items()
                if value not in (None, '')
            },
        }
        return self.add(
            '',
            'env-integration',
            'active-directory',
            _required_string(label, 'label'),
            parameters,
        )

    def authorize_active_directory(self, credential_id, endpoint_ids):
        """Add endpoint authorization without rotating AD secret material."""
        credential_id = normalize_credential_id(credential_id)
        record = self._credential_record(credential_id)
        credential_type = str(record.get('type') or '').strip()
        if credential_type != 'active-directory':
            raise ValueError(
                f'credential {credential_id!r} is not active-directory'
            )
        existing = record.get('endpointIds') or record.get('endpoint_ids') or []
        endpoint_ids = list(dict.fromkeys([
            *[
                _required_string(value, 'existing endpoint ID')
                for value in existing
            ],
            *_required_strings(endpoint_ids, 'endpoint IDs'),
        ]))
        label = _required_string(
            record.get('name') or record.get('label'),
            'credential label',
        )
        return self.api.post('broker', {
            'Operation': 'update',
            'CredentialID': credential_id,
            'Category': 'env-integration',
            'Type': 'active-directory',
            'Format': ['env'],
            'Parameters': {
                'label': label,
                'endpointIds': endpoint_ids,
            },
        })

    def add_ephemeral(self, parameters):
        """Store one short-lived HITL credential payload in the broker.

        Callers must pass plaintext values only in ``parameters``. The broker
        returns an opaque credential reference; only that reference may be
        used as a conversation interaction response.
        """
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError('ephemeral credential parameters are required')
        if any(
            not isinstance(key, str) or not key or not isinstance(value, str)
            or not value
            for key, value in parameters.items()
        ):
            raise ValueError(
                'ephemeral credential parameters must be non-empty strings'
            )
        return self.api.post('broker', {
            'Operation': 'add',
            'Category': 'env-integration',
            'Type': 'ephemeral',
            'Parameters': dict(parameters),
        })

    def delete_ephemeral(self, credential_id):
        """Best-effort cleanup primitive for an unused ephemeral secret."""
        if not isinstance(credential_id, str) or not credential_id.strip():
            raise ValueError('ephemeral credential ID is required')
        return self.api.delete('broker', {
            'CredentialID': credential_id.strip(),
            'Category': 'env-integration',
            'Type': 'ephemeral',
        }, params={})

    def _credential_record(self, credential_id):
        credentials, _ = self.list()
        matches = [
            credential for credential in credentials
            if normalize_credential_id(
                credential.get('credentialId')
                or credential.get('credential_id')
                or credential.get('key')
            ) == credential_id
        ]
        if len(matches) != 1:
            raise ValueError(f'credential {credential_id!r} was not found')
        return matches[0]

    def delete(self, credential_id, resource_key, type):
        """
        Delete a credential via the credential broker.

        :param credential_id: The ID of the credential to delete
        :type credential_id: str
        :param resource_key: The resource key the credential is attached to
            (e.g., account key, web-application key)
        :type resource_key: str
        :param type: The credential type (e.g., 'web-auth', 'active-directory', 'burp-authentication')
        :type type: str
        :return: The response from the broker API
        :rtype: dict
        """
        request = {
            'CredentialID': credential_id,
            'ResourceKey': resource_key,
            'Type': type,
        }
        return self.api.delete('broker', request, params={})

    def list(self, offset=None, pages=100000, resource_key=None):
        """
        List credentials available to the current principal.

        :param offset: The offset of the page you want to retrieve results. If not supplied, retrieves from first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :param resource_key: Scope to credentials attached to this WebApplication
            (follows its HAS_CREDENTIAL edges) instead of listing all credentials.
        :type resource_key: str or None
        :return: A tuple containing (list of credential entities, next page offset)
        :rtype: tuple
        """
        if resource_key:
            edges = self.api.search.relationships(resource_key, ['HAS_CREDENTIAL'])
            return [e['target'] for e in edges], None
        return self.api.search.by_key_prefix('#credential', offset=offset, pages=pages)

    def get(self, credential_id, category, type, format, resolution='by-target',
            resource_key=None, **parameters):
        """
        Get a specific credential using the credential broker.

        :param credential_id: The ID of the credential to retrieve. Required for
            resolution='by-target'; optional for 'from-parent' (broker walks the
            graph if empty).
        :type credential_id: str
        :param category: The category of the credential ('integration', 'cloud', 'env-integration')
        :type category: str
        :param type: The type of credential ('aws', 'gcp', 'azure', 'static', 'ssh_key', 'json', 'default')
        :type type: str
        :param format: The format of the credential response ('token', 'file', 'env')
        :type format: str or list
        :param resolution: How the broker should locate the credential. One of
            'by-target' (use credential_id as-is; default) or 'from-parent'
            (walk DISCOVERED ancestors of resource_key).
        :type resolution: str
        :param resource_key: Asset/resource key the credential is scoped to.
            Required when resolution='from-parent'.
        :type resource_key: str or None
        :param parameters: Additional parameters required for the credential request (e.g., region, role_arn)
        :type parameters: dict
        :return: The processed credential response based on the requested format
        :rtype: dict or str
        """
        # credential-process is a client-side format; the broker receives 'token'
        broker_format = format
        primary = format[0] if isinstance(format, list) else format
        if primary == 'credential-process':
            broker_format = ['token'] if isinstance(format, list) else 'token'

        request = {
            'Operation': 'get',
            'CredentialID': credential_id,
            'Category': category,
            'Type': type,
            'Format': broker_format,
            'Resolution': resolution,
            'Parameters': parameters,
        }
        if resource_key:
            request['ResourceKey'] = resource_key
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

        if primary_format == 'credential-process':
            cred = response.get('credentialValue')
            if not cred:
                raise ValueError('Broker response missing credentialValue for credential-process format')
            return json.dumps({
                'Version': 1,
                'AccessKeyId': cred['accessKeyId'],
                'SecretAccessKey': cred['secretAccessKey'],
                'SessionToken': cred['sessionToken'],
                'Expiration': cred['expiration']
            }, separators=(',', ':'))

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
        if isinstance(result, dict) and 'files' in result:
            output_lines = [result['message']]
            for file_path in result['files']:
                output_lines.append(f"  {file_path}")
            return '\n'.join(output_lines)
        elif isinstance(result, str):
            return result
        else:
            return json.dumps(result, indent=2)


def normalize_credential_id(reference):
    reference = str(reference or '').strip()
    if reference.startswith('#credential#'):
        reference = reference.rsplit('#', 1)[-1].strip()
    if not reference:
        raise ValueError('credential ID is required')
    return reference


def _required_string(value, name):
    value = str(value or '').strip()
    if not value:
        raise ValueError(f'{name} is required')
    return value


def _required_strings(values, name):
    normalized = [
        _required_string(value, name.removesuffix('s'))
        for value in values or []
    ]
    if not normalized:
        raise ValueError(f'{name} are required')
    return normalized
