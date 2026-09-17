import json

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from rich.console import Console
from praetorian_cli.ui.aegis.commands.job import complete as complete_job, handle_job
from praetorian_cli.ui.aegis.commands.job_helpers import CapabilityCompleter, extract_target_type
from rich.prompt import Confirm
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.selected_agent = MockAgent()


class V2Endpoint:
    hostname = "sensor"
    endpoint_id = "endpoint-1"
    version = "v2"
    kind = "aegis"
    os = "linux"

    @property
    def client_id(self):
        raise AssertionError("v2 jobs must not inspect legacy client_id")

    @property
    def has_tunnel(self):
        raise AssertionError("v2 jobs must not inspect legacy tunnel state")

    @property
    def health_check(self):
        raise AssertionError("v2 jobs must not inspect legacy tunnel state")


def _select_v2_endpoint(menu):
    menu.selected_agent = V2Endpoint()


def _endpoint_capabilities(*names, target='asset'):
    return [
        {
            'name': name,
            'target': [target],
            'description': f'{name} endpoint capability',
            'executor': 'chariot',
        }
        for name in names
    ]


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


def test_v2_job_capabilities_lists_guard_endpoint_catalog_without_legacy_calls():
    responses = {
        'endpoint_capabilities': _endpoint_capabilities('dynamic-scan', 'portscan'),
        'list_caps': {
            'capabilities': [
                {'name': 'windows-smb', 'description': 'Legacy v1-only capability'},
            ],
        },
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_job(menu, ['capabilities'])

    output = menu.console.export_text()
    assert 'Aegis v2 Endpoint Capabilities' in output
    assert 'dynamic-scan' in output
    assert 'portscan' in output
    assert 'windows-smb' not in output
    assert menu.sdk.capabilities.calls == [{
        'method': 'list',
        'name': '',
        'target': '',
        'executor': '',
        'surface': '',
        'endpoint_kind': 'aegis',
    }]
    assert menu.sdk.aegis.calls == []
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_completion_uses_guard_endpoint_catalog():
    responses = {'endpoint_capabilities': _endpoint_capabilities('dynamic-scan', 'other-scan')}
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)

    assert complete_job(menu, 'dyn', ['job', 'run']) == ['dynamic-scan']
    assert complete_job(menu, 'oth', ['job', 'run']) == ['other-scan']
    assert menu.sdk.capabilities.calls == [{
        'method': 'list',
        'name': '',
        'target': '',
        'executor': '',
        'surface': '',
        'endpoint_kind': 'aegis',
    }]


def test_v2_job_run_help_does_not_use_v1_guard_or_create_job():
    menu = Menu()
    _select_v2_endpoint(menu)

    handle_job(menu, ['run', 'portscan', '--help'])

    output = "\n".join(menu.console.lines)
    assert 'Aegis v2 Job Run' in output
    assert 'only supported for Aegis v1' not in output
    assert menu.sdk.aegis.calls == []
    assert menu.sdk.assets.calls == []
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_portscan_uses_existing_asset_and_endpoint_config():
    responses = {
        'endpoint_capabilities': _endpoint_capabilities('portscan'),
        'asset': {
            'key': '#asset#10.0.0.7#10.0.0.7',
            'dns': '10.0.0.7',
            'name': '10.0.0.7',
            'status': 'A',
        }
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)

    handle_job(menu, ['run', 'portscan', '10.0.0.7', '--yes'])

    assert menu.sdk.aegis.calls == []
    assert menu.sdk.assets.calls == [{
        'method': 'get',
        'key': '#asset#10.0.0.7#10.0.0.7',
        'details': False,
    }]
    assert len(menu.sdk.jobs.calls) == 1
    job_call = menu.sdk.jobs.calls[0]
    assert job_call['target_key'] == '#asset#10.0.0.7#10.0.0.7'
    assert job_call['capabilities'] == ['portscan']
    assert json.loads(job_call['config']) == {'endpoint_agent_id': 'endpoint-1'}
    assert job_call['credentials'] is None
    assert menu.paused is True


def test_v2_smb_secrets_prompts_for_and_forwards_ad_credential(monkeypatch):
    target_key = '#repository#smb://files.example.test/share#share'
    responses = {
        'endpoint_capabilities': _endpoint_capabilities('secrets', target='repository'),
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job_v2._select_credentials',
        lambda _menu: (
            '#credential#env-integration#active-directory#credential-1',
            'AD Credential',
        ),
    )

    handle_job(menu, ['run', 'secrets', '--key', target_key, '--yes'])

    assert len(menu.sdk.jobs.calls) == 1
    job_call = menu.sdk.jobs.calls[0]
    assert job_call['target_key'] == target_key
    assert job_call['capabilities'] == ['secrets']
    assert job_call['credentials'] == ['credential-1']
    assert json.loads(job_call['config']) == {'endpoint_agent_id': 'endpoint-1'}


def test_v2_git_secrets_does_not_prompt_for_ad_credential(monkeypatch):
    target_key = '#repository#https://github.com/example/project#project'
    responses = {
        'endpoint_capabilities': _endpoint_capabilities('secrets', target='repository'),
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job_v2._select_credentials',
        lambda _menu: pytest.fail('Git repository credentials come from Repository.Secret'),
    )

    handle_job(menu, ['run', 'secrets', '--key', target_key, '--yes'])

    assert menu.sdk.jobs.calls[0]['credentials'] is None


def test_v2_umber_check_prompts_for_and_forwards_ad_credential(monkeypatch):
    target_key = '#addomain#foobar.local#S-1-5-21-3022298462-3966147958-3640882514'
    responses = {
        'endpoint_capabilities': _endpoint_capabilities(
            'linux-ad-umber-check',
            target='addomain',
        ),
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job_v2._select_credentials',
        lambda _menu: (
            '#credential#env-integration#active-directory#credential-1',
            'AD Credential',
        ),
    )

    handle_job(menu, ['run', 'linux-ad-umber-check', '--key', target_key, '--yes'])

    assert len(menu.sdk.jobs.calls) == 1
    job_call = menu.sdk.jobs.calls[0]
    assert job_call['target_key'] == target_key
    assert job_call['capabilities'] == ['linux-ad-umber-check']
    assert json.loads(job_call['config']) == {'endpoint_agent_id': 'endpoint-1'}
    assert job_call['credentials'] == ['credential-1']
    assert menu.paused is True


def test_v2_umber_collect_accepts_explicit_ad_credential(monkeypatch):
    target_key = '#addomain#foobar.local#S-1-5-21-3022298462-3966147958-3640882514'
    responses = {
        'endpoint_capabilities': _endpoint_capabilities(
            'linux-ad-umber-collect',
            target='addomain',
        ),
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job_v2._select_credentials',
        lambda _menu: pytest.fail('explicit credential must skip the picker'),
    )

    handle_job(menu, [
        'run',
        'linux-ad-umber-collect',
        '--key',
        target_key,
        '--credential',
        'credential-1',
        '--config',
        '{"Server":"192.0.2.179","DNSServer":"192.0.2.179"}',
        '--yes',
    ])

    assert len(menu.sdk.jobs.calls) == 1
    job_call = menu.sdk.jobs.calls[0]
    assert job_call['credentials'] == ['credential-1']
    assert json.loads(job_call['config']) == {
        'Server': '192.0.2.179',
        'DNSServer': '192.0.2.179',
        'endpoint_agent_id': 'endpoint-1',
    }


def test_v2_umber_collect_rejects_explicit_non_ad_credential():
    target_key = '#addomain#foobar.local#S-1-5-21-3022298462-3966147958-3640882514'
    responses = {
        'endpoint_capabilities': _endpoint_capabilities(
            'linux-ad-umber-collect',
            target='addomain',
        ),
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)

    handle_job(menu, [
        'run',
        'linux-ad-umber-collect',
        '--key',
        target_key,
        '--credential',
        '#credential#cloud#aws#credential-1',
        '--yes',
    ])

    output = "\n".join(menu.console.lines)
    assert 'requires an Active Directory credential' in output
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_portscan_requires_existing_asset_without_auto_create():
    menu = Menu(responses={'endpoint_capabilities': _endpoint_capabilities('portscan')})
    _select_v2_endpoint(menu)

    handle_job(menu, ['run', 'portscan', '10.0.0.7', '--yes'])

    output = "\n".join(menu.console.lines)
    assert 'No existing asset found for 10.0.0.7' in output
    assert menu.sdk.assets.calls == [{
        'method': 'get',
        'key': '#asset#10.0.0.7#10.0.0.7',
        'details': False,
    }]
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_cancel_does_not_add_asset_or_job(monkeypatch):
    responses = {
        'endpoint_capabilities': _endpoint_capabilities('portscan'),
        'asset': {
            'key': '#asset#10.0.0.7#10.0.0.7',
            'dns': '10.0.0.7',
            'name': '10.0.0.7',
            'status': 'A',
        }
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job_v2.Confirm.ask', lambda *a, **k: False)

    handle_job(menu, ['run', 'portscan', '10.0.0.7'])

    output = "\n".join(menu.console.lines)
    assert 'Cancelled' in output
    assert menu.sdk.assets.calls == [{
        'method': 'get',
        'key': '#asset#10.0.0.7#10.0.0.7',
        'details': False,
    }]
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_rejects_unsupported_capability_without_side_effects():
    menu = Menu(responses={
        'endpoint_capabilities': _endpoint_capabilities('portscan'),
        'capabilities': {
            'windows-smb': {'name': 'windows-smb', 'description': 'Legacy v1-only capability', 'target': 'asset'},
        },
    })
    _select_v2_endpoint(menu)

    handle_job(menu, ['run', 'windows-smb', '10.0.0.7', '--yes'])

    output = "\n".join(menu.console.lines)
    assert "Invalid Aegis v2 capability: 'windows-smb'" in output
    assert menu.sdk.aegis.calls == []
    assert menu.sdk.assets.calls == []
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_run_rejects_legacy_config_without_side_effects():
    menu = Menu(responses={'endpoint_capabilities': _endpoint_capabilities('portscan')})
    _select_v2_endpoint(menu)

    handle_job(menu, ['run', 'portscan', '10.0.0.7', '--config', '{"client_id":"C.1"}', '--yes'])

    output = "\n".join(menu.console.lines)
    assert 'legacy config keys: client_id' in output
    assert menu.sdk.aegis.calls == []
    assert menu.sdk.assets.calls == []
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_v2_job_list_filters_recent_jobs_by_endpoint_config():
    responses = {
        'jobs': [
            {
                'key': '#job#10.0.0.7#10.0.0.7#portscan#old',
                'status': 'JQ#1',
                'created': 9,
                'capabilities': ['portscan'],
                'config': {'endpoint_agent_id': 'endpoint-1'},
            },
            {
                'key': '#job#10.0.0.8#10.0.0.8#portscan#other',
                'status': 'JQ#1',
                'created': '2026-08-25T11:09:06Z',
                'capabilities': ['portscan'],
                'config': {'endpoint_agent_id': 'other-endpoint'},
            },
            {
                'key': '#job#10.0.0.9#10.0.0.9#portscan#new',
                'status': 'JQ#1',
                'created': 10,
                'capabilities': ['portscan'],
                'config': {'endpoint_agent_id': 'endpoint-1'},
            },
        ],
    }
    menu = Menu(responses=responses)
    _select_v2_endpoint(menu)
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_job(menu, ['list'])

    output = menu.console.export_text()
    assert 'Recent Jobs for endpoint endpoint-1' in output
    assert 'portscan' in output
    assert output.find('new') < output.find('old')
    assert menu.sdk.jobs.calls == [{
        'method': 'list',
        'prefix_filter': '',
        'offset': None,
        'pages': 1,
    }]
    assert menu.sdk.aegis.calls == []
    assert menu.paused is True


def test_capability_completer_accepts_list_target():
    completer = CapabilityCompleter([
        {
            'name': 'linux-enum-linpeas',
            'description': 'Linux enumeration',
            'target': ['asset'],
        }
    ])

    completions = list(completer.get_completions(Document('linux'), CompleteEvent()))

    assert len(completions) == 1
    assert completions[0].text == 'linux-enum-linpeas'
    assert '[asset]' in str(completions[0].display_meta)


def test_extract_target_type_normalizes_empty_and_non_string_lists():
    assert extract_target_type({'target': []}) == 'asset'
    assert extract_target_type({'target': [123]}) == '123'


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


def test_v1_smb_secrets_uses_repository_target_and_ad_credential(monkeypatch):
    target_key = '#repository#smb://files.example.test/share#share'
    responses = {
        'capabilities': {
            'secrets': {
                'name': 'secrets',
                'description': 'Titus SMB secret scan',
                'target': 'repository',
                'parameters': [],
            },
        },
    }
    menu = Menu(responses=responses)
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job._interactive_capability_picker',
        lambda _menu, _suggested=None: 'secrets',
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job._select_credentials',
        lambda _menu: (
            '#credential#env-integration#active-directory#credential-1',
            'AD Credential',
        ),
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.aegis.commands.job.Confirm.ask',
        lambda *args, **kwargs: True,
    )

    handle_job(menu, ['run', 'secrets', target_key])

    assert len(menu.sdk.jobs.calls) == 1
    job_call = menu.sdk.jobs.calls[0]
    assert job_call['target_key'] == target_key
    assert job_call['capabilities'] == ['secrets']
    assert job_call['credentials'] == ['credential-1']


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
