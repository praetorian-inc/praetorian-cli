import pytest
import os
import tempfile
from configparser import ConfigParser
from unittest.mock import patch, MagicMock

from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.test.utils import setup_chariot, make_test_values


@pytest.mark.coherence
class TestAPIKey:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)
        
        self.original_api_key_id = os.environ.get('PRAETORIAN_CLI_API_KEY_ID')
        self.original_api_key = os.environ.get('PRAETORIAN_CLI_API_KEY')
        
        self.test_api_key_id = os.environ.get('CHARIOT_UAT_API_KEY_ID', 'test_key_id')
        self.test_api_key = os.environ.get('CHARIOT_UAT_API_KEY', 'test_key_value')
        self.use_real_keys = 'CHARIOT_UAT_API_KEY_ID' in os.environ and 'CHARIOT_UAT_API_KEY' in os.environ

    def test_api_key_environment_variables(self):
        os.environ['PRAETORIAN_CLI_API_KEY_ID'] = self.test_api_key_id
        os.environ['PRAETORIAN_CLI_API_KEY'] = self.test_api_key
        
        keychain = Keychain()
        keychain.load()
        
        assert keychain.api_key_id() == self.test_api_key_id
        assert keychain.api_key() == self.test_api_key
        assert keychain.has_api_key() == True
        
        if self.use_real_keys:
            token = keychain.token()
            assert token is not None
            assert len(token) > 0
        else:
            with patch('requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'token': 'mock_jwt_token'}
                mock_get.return_value = mock_response
                
                token = keychain.token()
                assert token == 'mock_jwt_token'
                mock_get.assert_called_once()
        
        del os.environ['PRAETORIAN_CLI_API_KEY_ID']
        del os.environ['PRAETORIAN_CLI_API_KEY']

    def test_api_key_ini_configuration(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            config = ConfigParser()
            config.add_section('United States')
            config.set('United States', 'username', 'test_user')
            config.set('United States', 'password', 'test_pass')
            config.set('United States', 'api', 'https://uat.chariot.praetorian.com')
            config.set('United States', 'client_id', 'test_client')
            config.set('United States', 'api_key_id', self.test_api_key_id)
            config.set('United States', 'api_key', self.test_api_key)
            config.write(f)
            temp_keychain_path = f.name
        
        try:
            keychain = Keychain(filepath=temp_keychain_path)
            keychain.load()
            
            assert keychain.api_key_id() == self.test_api_key_id
            assert keychain.api_key() == self.test_api_key
            assert keychain.has_api_key() == True
            
            if self.use_real_keys:
                token = keychain.token()
                assert token is not None
                assert len(token) > 0
            else:
                with patch('requests.get') as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'token': 'mock_jwt_token'}
                    mock_get.return_value = mock_response
                    
                    token = keychain.token()
                    assert token == 'mock_jwt_token'
                    mock_get.assert_called_once()
            
        finally:
            os.unlink(temp_keychain_path)

    def test_api_key_authentication_priority(self):
        os.environ['PRAETORIAN_CLI_API_KEY_ID'] = self.test_api_key_id
        os.environ['PRAETORIAN_CLI_API_KEY'] = self.test_api_key
        os.environ['PRAETORIAN_CLI_USERNAME'] = 'test_user'
        os.environ['PRAETORIAN_CLI_PASSWORD'] = 'test_pass'
        
        try:
            keychain = Keychain()
            keychain.load()
            
            assert keychain.has_api_key() == True
            
            if self.use_real_keys:
                token = keychain.token()
                assert token is not None
            else:
                with patch('requests.get') as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'token': 'mock_jwt_token'}
                    mock_get.return_value = mock_response
                    
                    token = keychain.token()
                    assert token == 'mock_jwt_token'
                    mock_get.assert_called_once()
            
        finally:
            for var in ['PRAETORIAN_CLI_API_KEY_ID', 'PRAETORIAN_CLI_API_KEY', 
                       'PRAETORIAN_CLI_USERNAME', 'PRAETORIAN_CLI_PASSWORD']:
                if var in os.environ:
                    del os.environ[var]

    def test_api_key_fallback_to_username_password(self):
        for var in ['PRAETORIAN_CLI_API_KEY_ID', 'PRAETORIAN_CLI_API_KEY']:
            if var in os.environ:
                del os.environ[var]
        
        keychain = Keychain()
        keychain.load()
        
        assert keychain.has_api_key() == False
        
        with patch('boto3.client') as mock_boto3:
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.return_value = {
                'AuthenticationResult': {
                    'IdToken': 'mock_cognito_token',
                    'ExpiresIn': 3600
                }
            }
            mock_boto3.return_value = mock_cognito
            
            token = keychain.token()
            assert token == 'mock_cognito_token'
            mock_cognito.initiate_auth.assert_called_once()

    def test_api_key_sdk_integration(self):
        os.environ['PRAETORIAN_CLI_API_KEY_ID'] = self.test_api_key_id
        os.environ['PRAETORIAN_CLI_API_KEY'] = self.test_api_key
        
        try:
            keychain = Keychain()
            keychain.load()
            
            assert keychain.has_api_key() == True
            
            if self.use_real_keys:
                from praetorian_cli.sdk.chariot import Chariot
                sdk = Chariot(keychain)
                
                results, _ = sdk.assets.list()
                assert isinstance(results, list)
            else:
                with patch('requests.get') as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'token': 'mock_jwt_token'}
                    mock_get.return_value = mock_response
                    
                    headers = keychain.headers()
                    assert 'Authorization' in headers
                    assert headers['Authorization'] == 'Bearer mock_jwt_token'
                    assert headers['Content-Type'] == 'application/json'
            
        finally:
            for var in ['PRAETORIAN_CLI_API_KEY_ID', 'PRAETORIAN_CLI_API_KEY']:
                if var in os.environ:
                    del os.environ[var]

    def teardown_class(self):
        if self.original_api_key_id:
            os.environ['PRAETORIAN_CLI_API_KEY_ID'] = self.original_api_key_id
        elif 'PRAETORIAN_CLI_API_KEY_ID' in os.environ:
            del os.environ['PRAETORIAN_CLI_API_KEY_ID']
            
        if self.original_api_key:
            os.environ['PRAETORIAN_CLI_API_KEY'] = self.original_api_key
        elif 'PRAETORIAN_CLI_API_KEY' in os.environ:
            del os.environ['PRAETORIAN_CLI_API_KEY']
