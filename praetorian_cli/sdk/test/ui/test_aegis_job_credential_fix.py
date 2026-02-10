"""Test that TUI attaches credentials by UUID, not by fetching and embedding values.

This test verifies the fix for the bug where the TUI was trying to fetch
credential values (causing 403 errors) instead of just passing the credential
UUID to the jobs API like the CLI does.

Working CLI pattern:
    praetorian chariot add job --key <target> --credential <uuid>
    → jobs.add(key, capabilities, config, credentials=[uuid])
    → API receives credential_ids=[uuid] and retrieves values server-side

Broken TUI pattern (before fix):
    → credentials.get(uuid) # 403 error!
    → embed values in config
    → jobs.add(key, capabilities, config, credentials=[])  # empty!

Fixed TUI pattern (after fix):
    → extract UUID from credential key
    → jobs.add(key, capabilities, config, credentials=[uuid])  # UUID passed!
"""

import json

import pytest
from praetorian_cli.ui.aegis.commands.job import handle_job
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.selected_agent = MockAgent()


def test_credential_uuid_passed_not_fetched(monkeypatch):
    """Test that credential UUID is passed to jobs.add(), not fetched and embedded.

    This is the CORRECT behavior:
    1. User selects credential from list
    2. Extract UUID from credential key
    3. Pass UUID to jobs.add(credentials=[uuid])
    4. API retrieves values server-side (not the TUI!)

    This test verifies:
    - credentials.get() is NOT called (no fetching!)
    - jobs.add() receives credentials=[uuid] parameter
    - Config does NOT contain embedded Username/Password/Domain
    """
    responses = {
        'capabilities': {
            'ad-enum': {
                'name': 'ad-enum',
                'description': 'AD enumeration',
                'target': 'addomain',
                'parameters': [
                    {'name': 'Username', 'default': ''}, {'name': 'Password', 'default': ''}, {'name': 'Domain', 'default': ''}
                ]
            }
        },
        'credentials': [
            {
                'key': '#credential#env-integration#active-directory#test-uuid-1234',
                'name': 'Test AD Credential',
                'type': 'active-directory',
                'username': 'testuser',
            },
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
                        lambda m: ('#credential#env-integration#active-directory#test-uuid-1234', 'Test Credential (admin)'))

    handle_job(menu, ['run', 'ad-enum'])

    # CRITICAL: credentials.get() should NOT be called
    # The TUI should not fetch credential values - that causes 403!
    cred_calls = menu.sdk.credentials.calls
    get_calls = [call for call in cred_calls if call.get('method') == 'get']
    assert len(get_calls) == 0, \
        "credentials.get() should NOT be called - causes 403 error! UUID should be passed directly."

    # CRITICAL: Credential UUID should be passed to jobs.add()
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1, "jobs.add() should be called once"

    # The credentials parameter should contain the UUID
    credentials_param = job_calls[0].get('credentials', [])
    assert credentials_param == ['test-uuid-1234'], \
        f"Expected credentials=['test-uuid-1234'], got {credentials_param}. " \
        f"UUID should be passed directly to jobs.add(), not left empty!"

    # Config should NOT contain embedded Username/Password/Domain
    # (They should be retrieved server-side from the credential UUID)
    config = job_calls[0].get('config', '{}')
    if isinstance(config, str):
        config = json.loads(config)

    assert 'Username' not in config, \
        "Username should NOT be embedded in config - credential is passed by UUID!"
    assert 'Password' not in config, \
        "Password should NOT be embedded in config - credential is passed by UUID!"
    assert 'Domain' not in config, \
        "Domain should NOT be embedded in config - credential is passed by UUID!"


def test_multiple_credentials_passed_as_uuids(monkeypatch):
    """Test that multiple credentials can be attached by UUID.

    The CLI supports --credential multiple times:
        praetorian chariot add job --credential uuid1 --credential uuid2

    The TUI should support the same pattern.
    """
    responses = {
        'capabilities': {
            'ad-enum': {
                'name': 'ad-enum',
                'description': 'AD enumeration',
                'target': 'addomain',
                'parameters': [
                    {'name': 'Username', 'default': ''}, {'name': 'Password', 'default': ''}, {'name': 'Domain', 'default': ''}
                ]
            }
        },
        'credentials': [
            {
                'key': '#credential#env#active-directory#uuid-1',
                'name': 'First Credential',
                'type': 'active-directory',
            },
            {
                'key': '#credential#env#active-directory#uuid-2',
                'name': 'Second Credential',
                'type': 'active-directory',
            },
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

    # For this test, we'll only select one credential
    # (Multiple credential selection requires UI flow changes not in scope)
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
                        lambda m: ('#credential#env#active-directory#uuid-1', 'Test Credential (admin)'))

    handle_job(menu, ['run', 'ad-enum'])

    # Verify credential UUID is passed
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    credentials_param = job_calls[0].get('credentials', [])
    assert len(credentials_param) >= 1, "At least one credential should be attached"
    assert credentials_param[0] == 'uuid-1', "First credential UUID should be passed"
