import pytest
from praetorian_cli.ui.aegis.commands.job import handle_job
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.selected_agent = MockAgent()


def test_job_run_addomain_uses_asset_key_from_database(monkeypatch):
    """Test that addomain jobs use the actual asset key from the database, not constructed keys.

    When running a job against an AD domain, the target_key should be the actual asset key
    from the database (which includes the SID), not a constructed key like #addomain#{domain}#{domain}.

    Expected format: #addomain#<domain>#<SID>
    Example: #addomain#corp.local#S-1-5-21-123456789-123456789-123456789-1001
    NOT: #addomain#corp.local#corp.local
    """
    # Mock response with actual AD domain asset (with SID in key)
    domain_asset_key = '#addomain#corp.local#S-1-5-21-123456789-123456789-123456789-1001'

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
        'domains': ['corp.local'],
        'assets': [
            {
                'key': domain_asset_key,
                'dns': 'corp.local',
                'name': 'S-1-5-21-123456789-123456789-123456789-1001',
                'type': 'addomain',
                'status': 'A'
            }
        ],
        'job': {
            'key': '#job#corp.local#ad-enum#1234567890',
            'status': 'JQ',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    # Mock user interactions: confirm suggested capability, decline credentials, large artifact, confirm running the job
    confirm_index = [0]
    confirm_responses = [True, False, True, True]  # Confirm suggested capability, Decline credentials, Large artifact, Run job

    def mock_confirm_ask(prompt, **kwargs):
        result = confirm_responses[confirm_index[0]]
        confirm_index[0] += 1
        return result

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', mock_confirm_ask)
    # Mock Prompt.ask to return defaults for parameter configuration
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Prompt.ask', lambda prompt, **kw: kw.get('default', ''))
    # Mock the fuzzy-picker domain selector directly
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job._select_domain', lambda m: 'corp.local')

    # Run the job
    handle_job(menu, ['run', 'ad-enum'])

    # Verify the job was created with the correct target_key from the database
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1, "Expected exactly one job call"
    assert job_calls[0]['capabilities'] == ['ad-enum'], "Capability should be ad-enum"

    # CRITICAL: The target_key MUST be the actual asset key from database (with SID)
    actual_target_key = job_calls[0]['target_key']
    assert actual_target_key == domain_asset_key, \
        f"Expected target_key to be the actual asset key '{domain_asset_key}' (with SID), " \
        f"but got '{actual_target_key}'"

    # Verify it's NOT the incorrect constructed format
    incorrect_format = '#addomain#corp.local#corp.local'
    assert actual_target_key != incorrect_format, \
        f"target_key should NOT be constructed as '{incorrect_format}', " \
        f"it must use the actual asset key from the database with SID"


def test_job_run_addomain_queries_assets_for_domain(monkeypatch):
    """Test that when running an addomain job, we query assets to find the domain's asset key."""
    domain_asset_key = '#addomain#example.local#S-1-5-21-999888777-666555444-333222111-500'

    responses = {
        'capabilities': {
            'windows-ad-sharphound': {
                'name': 'windows-ad-sharphound',
                'description': 'Run Sharphound collector',
                'target': 'addomain',
                'parameters': [
                    {'name': 'Username', 'default': ''}, {'name': 'Password', 'default': ''}, {'name': 'Domain', 'default': ''}
                ]
            }
        },
        'domains': ['example.local'],
        'assets': [
            {
                'key': domain_asset_key,
                'dns': 'example.local',
                'name': 'S-1-5-21-999888777-666555444-333222111-500',
                'type': 'addomain',
                'status': 'A'
            }
        ],
        'job': {
            'key': '#job#example.local#windows-ad-sharphound#1234567890',
            'status': 'JQ',
        },
        'config': {},
    }
    menu = Menu(responses=responses)

    confirm_responses = [True, False, True, True]  # Confirm suggested capability, Decline credentials, Large artifact, Run job
    confirm_index = [0]

    def mock_confirm_ask(prompt, **kwargs):
        result = confirm_responses[confirm_index[0]]
        confirm_index[0] += 1
        return result

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', mock_confirm_ask)
    # Mock Prompt.ask to return defaults for parameter configuration
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Prompt.ask', lambda prompt, **kw: kw.get('default', ''))
    # Mock the fuzzy-picker domain selector directly
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job._select_domain', lambda m: 'example.local')

    handle_job(menu, ['run', 'windows-ad-sharphound'])

    # Verify assets were queried to get the actual domain key
    asset_calls = menu.sdk.assets.calls
    assert len(asset_calls) >= 1, "Expected at least one call to assets.list to find domain asset"

    # Verify the first asset call was to query for the domain
    first_asset_call = asset_calls[0]
    assert first_asset_call['method'] == 'list', "Should call assets.list to find domain"
    assert '#addomain#example.local' in first_asset_call.get('key_prefix', ''), \
        "Should query assets with #addomain#{domain} prefix"

    # Verify job was created with the correct asset key
    job_calls = menu.sdk.jobs.calls
    assert len(job_calls) == 1
    assert job_calls[0]['target_key'] == domain_asset_key
