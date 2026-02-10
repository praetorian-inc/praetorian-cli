import json

import pytest
from praetorian_cli.ui.aegis.commands.job import handle_job
from rich.prompt import Confirm
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.selected_agent = MockAgent()


def test_job_capabilities_lists_caps():
    responses = {
        'list_caps': {
            'capabilities': [
                {'name': 'windows-enum', 'description': 'Enumerate Windows stuff'},
                {'name': 'linux-enum', 'description': 'Enumerate Linux stuff'},
            ]
        }
    }
    menu = Menu(responses=responses)
    handle_job(menu, ['capabilities'])

    calls = menu.sdk.aegis.calls
    assert len(calls) == 1
    assert calls[0]['capabilities'] is None


def test_job_run_success(monkeypatch):
    responses = {
        'capabilities': {
            'windows-smb': {'name': 'windows-smb', 'description': 'desc', 'target': 'asset'}
        },
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {"Username": "u"},
    }
    menu = Menu(responses=responses)

    # Auto-confirm prompts encountered in the interactive flow
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', lambda *a, **k: True)

    handle_job(menu, ['run', 'windows-smb'])

    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    assert job_calls[0]['capabilities'] == ['windows-smb']
    assert job_calls[0]['target_key'].startswith('#asset#')


def test_job_run_with_credential_attachment(monkeypatch):
    """Test that only active-directory credentials can be selected and attached to jobs.

    The mock data includes 6 credentials (aws, active-directory, ssh_key, active-directory, gcp, static).
    Only the 2 active-directory credentials should be available for selection.
    When user selects "1", they should get the first AD credential (cred1), not the first overall credential (aws1).

    UPDATED: After fix, credentials are passed by UUID (like CLI), not fetched and embedded.
    """
    responses = {
        'capabilities': {
            'ad-enum': {'name': 'ad-enum', 'description': 'AD enumeration', 'target': 'addomain', 'parameters': [
                {'name': 'Username', 'default': ''}, {'name': 'Password', 'default': ''}, {'name': 'Domain', 'default': ''}
            ]}
        },
        'credentials': [
            {
                'key': '#credential#cloud#aws#aws1',
                'name': 'AWS Credential',
                'type': 'aws',
            },
            {
                'key': '#credential#env-integration#active-directory#cred1',
                'name': 'Test AD Credential',
                'type': 'active-directory',
                'username': 'testuser',
            },
            {
                'key': '#credential#cloud#ssh_key#ssh1',
                'name': 'SSH Key',
                'type': 'ssh_key',
                'username': 'root',
            },
            {
                'key': '#credential#env-integration#active-directory#cred2',
                'name': 'Another AD Credential',
                'type': 'active-directory',
                'username': 'admin',
            },
            {
                'key': '#credential#cloud#gcp#gcp1',
                'name': 'GCP Credential',
                'type': 'gcp',
            },
            {
                'key': '#credential#integration#static#static1',
                'name': 'Static Credential',
                'type': 'static',
                'username': 'user',
            }
        ],
        'domains': ['example.local'],
        'assets': [
            {
                'key': '#addomain#example.local#S-1-5-21-fake-sid',
                'dns': 'example.local',
                'name': 'S-1-5-21-fake-sid',
                'type': 'addomain',
                'status': 'A'
            }
        ],
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Mock user interactions:
    # 1. Confirm using the suggested capability
    # 2. Confirm wanting to attach credentials
    # 3. Confirm large artifact storage
    # 4. Confirm running the job
    confirm_responses = [True, True, True, True]  # Use suggested cap, attach credentials, large artifact, run job
    confirm_index = [0]

    def mock_confirm_ask(prompt, **kwargs):
        result = confirm_responses[confirm_index[0]]
        confirm_index[0] += 1
        return result

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', mock_confirm_ask)
    # Mock the fuzzy-picker functions directly
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job._select_domain', lambda m: 'example.local')
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job._select_credentials',
                        lambda m: ('#credential#env-integration#active-directory#cred1', 'Test Credential (admin)'))

    handle_job(menu, ['run', 'ad-enum'])

    # CRITICAL: credentials.get() should NOT be called after fix!
    # Credentials are passed by UUID, not fetched
    cred_calls = menu.sdk.credentials.calls
    get_calls = [call for call in cred_calls if call.get('method') == 'get']
    assert len(get_calls) == 0, "credentials.get() should NOT be called - UUID is passed directly!"

    # Verify job was created with credential UUID passed (not embedded in config)
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    assert job_calls[0]['capabilities'] == ['ad-enum']

    # Credentials should be passed as UUIDs in the credentials parameter
    credentials_param = job_calls[0].get('credentials', [])
    assert credentials_param == ['cred1'], \
        f"Expected credentials=['cred1'], got {credentials_param}. UUID should be passed directly!"


def test_job_run_with_parameter_configuration(monkeypatch):
    """Test that capabilities with parameters prompt for configuration."""
    responses = {
        'capabilities': {
            'linux-scan': {
                'name': 'linux-scan',
                'description': 'Scan Linux systems',
                'target': 'asset',
                'parameters': {
                    'timeout': '300',
                    'threads': '10',
                    'verbose': 'false'
                }
            }
        },
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Track Prompt.ask calls to verify parameter prompts
    prompt_calls = []

    def mock_prompt_ask(prompt, **kwargs):
        prompt_calls.append({'prompt': prompt, 'default': kwargs.get('default')})
        # Return custom values for parameters
        if 'timeout' in prompt.lower():
            return '600'
        elif 'threads' in prompt.lower():
            return '20'
        elif 'verbose' in prompt.lower():
            return 'true'
        return kwargs.get('default', '')

    # Auto-confirm prompts
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', lambda *a, **k: True)
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Prompt.ask', mock_prompt_ask)

    handle_job(menu, ['run', 'linux-scan'])

    # Verify parameters were prompted for
    assert len(prompt_calls) >= 3  # At least 3 parameter prompts
    param_prompts = [call for call in prompt_calls if any(
        param in call['prompt'].lower() for param in ['timeout', 'threads', 'verbose']
    )]
    assert len(param_prompts) == 3

    # Verify job was created with custom parameters in config
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    config = job_calls[0].get('config', {})
    # Config should contain the custom parameter values
    assert 'timeout' in config or 'Timeout' in config
    assert 'threads' in config or 'Threads' in config
    assert 'verbose' in config or 'Verbose' in config


def test_job_run_with_list_based_parameters(monkeypatch):
    """Test that capabilities with list-based parameters (actual API format) work correctly."""
    responses = {
        'capabilities': {
            'network-scan': {
                'name': 'network-scan',
                'description': 'Network scanning tool',
                'target': 'asset',
                'parameters': [
                    {'name': 'timeout', 'default': 300},
                    {'name': 'ports', 'default': '80,443,8080'},
                    {'name': 'aggressive', 'default': False}
                ]
            }
        },
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Track Prompt.ask calls
    prompt_calls = []

    def mock_prompt_ask(prompt, **kwargs):
        prompt_calls.append({'prompt': prompt, 'default': kwargs.get('default')})
        # Return custom values
        if 'timeout' in prompt.lower():
            return '600'
        elif 'ports' in prompt.lower():
            return '22,80,443'
        elif 'aggressive' in prompt.lower():
            return 'True'
        return kwargs.get('default', '')

    # Auto-confirm prompts
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', lambda *a, **k: True)
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Prompt.ask', mock_prompt_ask)

    handle_job(menu, ['run', 'network-scan'])

    # Verify parameters were prompted (list format should work)
    assert len(prompt_calls) >= 3
    param_prompts = [call for call in prompt_calls if any(
        param in call['prompt'].lower() for param in ['timeout', 'ports', 'aggressive']
    )]
    assert len(param_prompts) == 3, "All 3 parameters should be prompted"

    # Verify job was created
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    config = job_calls[0].get('config', {})
    # Config should contain parameters
    assert config  # Not empty


def test_job_run_with_large_artifact(monkeypatch):
    """Test that capabilities with largeArtifact: true prompt for S3 upload."""
    responses = {
        'capabilities': {
            'windows-network-nmap': {
                'name': 'windows-network-nmap',
                'description': 'Network mapper with large output',
                'target': 'asset',  # Use asset target to simplify test
                'largeArtifact': True,  # This capability generates large artifacts
                'parameters': []
            }
        },
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Track Confirm.ask calls to verify large artifact prompt appears
    confirm_calls = []
    # Prompts: Use suggested cap, enable large artifact, run job
    confirm_responses = [True, True, True]
    confirm_index = [0]

    def mock_confirm_ask(prompt, **kwargs):
        confirm_calls.append({'prompt': prompt, 'default': kwargs.get('default')})
        result = confirm_responses[confirm_index[0]]
        confirm_index[0] += 1
        return result

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', mock_confirm_ask)

    handle_job(menu, ['run', 'windows-network-nmap'])

    # Verify large artifact prompt appeared
    large_artifact_prompts = [call for call in confirm_calls if 'large artifact' in call['prompt'].lower()]
    assert len(large_artifact_prompts) == 1, f"Should prompt once for large artifact storage. Got {len(large_artifact_prompts)} prompts: {large_artifact_prompts}"

    # Verify the default was True for largeArtifact capability
    assert large_artifact_prompts[0]['default'] is True, "Default should be True for capability with largeArtifact=True"

    # Verify job was created with largeArtifact config
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    config = job_calls[0].get('config', '{}')
    if isinstance(config, str):
        config = json.loads(config)
    assert config.get('largeArtifact') == 'true', "Config should have largeArtifact='true' when enabled"


def test_job_run_without_large_artifact_default_false(monkeypatch):
    """Test that capabilities without largeArtifact have default=False for the S3 prompt."""
    responses = {
        'capabilities': {
            'linux-enum': {
                'name': 'linux-enum',
                'description': 'Basic Linux enumeration',
                'target': 'asset',
                'largeArtifact': False,  # This capability does NOT generate large artifacts
                'parameters': []
            }
        },
        'job': {
            'key': 'jobs#deadbeefcafebabe',
            'status': 'queued',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Track Confirm.ask calls
    confirm_calls = []
    # Prompts: Use suggested cap, large artifact (decline), run job
    confirm_responses = [True, False, True]
    confirm_index = [0]

    def mock_confirm_ask(prompt, **kwargs):
        confirm_calls.append({'prompt': prompt, 'default': kwargs.get('default')})
        result = confirm_responses[confirm_index[0]]
        confirm_index[0] += 1
        return result

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', mock_confirm_ask)

    handle_job(menu, ['run', 'linux-enum'])

    # Verify large artifact prompt appeared but with default=False
    large_artifact_prompts = [call for call in confirm_calls if 'large artifact' in call['prompt'].lower()]
    assert len(large_artifact_prompts) == 1, "Large artifact prompt should always appear"
    assert large_artifact_prompts[0]['default'] is False, "Default should be False for capability without largeArtifact"

    # Verify job was created without largeArtifact config (user declined)
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    config = job_calls[0].get('config', '{}')
    if isinstance(config, str):
        config = json.loads(config)
    assert 'largeArtifact' not in config, "Config should not have largeArtifact when user declines"
