import pytest
from praetorian_cli.ui.aegis.commands.job import handle_job
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


def test_job_run_success():
    responses = {'run': {'success': True, 'job_id': 'deadbeef', 'job_key': 'k', 'status': 'queued'}}
    menu = Menu(responses=responses)
    handle_job(menu, ['run', 'windows-smb', '--config', '{"Username":"u"}'])

    calls = menu.sdk.aegis.calls
    assert len(calls) == 1
    assert calls[0]['capabilities'] == ['windows-smb']
    assert calls[0]['config'] == '{"Username":"u"}'
