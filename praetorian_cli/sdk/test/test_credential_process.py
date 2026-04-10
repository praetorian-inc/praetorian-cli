import json
import pytest

from praetorian_cli.sdk.entities.credentials import Credentials


class TestCredentialProcessFormat:

    def setup_method(self):
        self.credentials = Credentials(api=None)

    def test_credential_process_format_returns_aws_json(self):
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, 'credential-process')
        parsed = json.loads(result)
        assert parsed == {
            'Version': 1,
            'AccessKeyId': 'ASIATESTACCESSKEY',
            'SecretAccessKey': 'testsecretkey123',
            'SessionToken': 'testsessiontoken456',
            'Expiration': '2026-04-10T12:00:00Z'
        }

    def test_credential_process_format_from_list(self):
        """credential-process works when format is passed as a list (as the CLI does)."""
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, ['credential-process'])
        parsed = json.loads(result)
        assert parsed['Version'] == 1
        assert parsed['AccessKeyId'] == 'ASIATESTACCESSKEY'

    def test_credential_process_output_is_compact_json(self):
        """Output must be a single line of JSON (no pretty-printing) for AWS CLI compatibility."""
        response = {
            'credentialValue': {
                'accessKeyId': 'ASIATESTACCESSKEY',
                'secretAccessKey': 'testsecretkey123',
                'sessionToken': 'testsessiontoken456',
                'expiration': '2026-04-10T12:00:00Z'
            }
        }
        result = self.credentials._process_credential_output(response, 'credential-process')
        assert '\n' not in result

    def test_format_output_returns_credential_process_string_as_is(self):
        """format_output should return a credential-process string unchanged."""
        raw = '{"Version":1,"AccessKeyId":"ASIATESTACCESSKEY","SecretAccessKey":"x","SessionToken":"y","Expiration":"z"}'
        output = self.credentials.format_output(raw)
        assert output == raw
