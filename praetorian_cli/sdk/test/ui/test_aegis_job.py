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
