import json

import pytest

from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK, MockAgent
from praetorian_cli.ui.aegis.commands.job import handle_job

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.selected_agent = MockAgent()


def mobile_responses(capability_parameters=None):
    return {
        'capabilities': {
            'android-device-survey': {
                'name': 'android-device-survey',
                'description': 'Inspects an installed Android application',
                'target': ['apk'],
                'surface': 'mobile',
                'parameters': capability_parameters or [],
            },
            'android-device-command': {
                'name': 'android-device-command',
                'description': 'Runs an operator-specified shell command',
                'target': ['apk'],
                'surface': 'mobile',
                'parameters': [{'name': 'command', 'default': ''}],
            },
        },
        'assets': [{'key': '#apk#com.bank.app', 'package': 'com.bank.app', 'versionName': '1.2.3'}],
        'endpoints': [
            {'endpointId': 'endpoint-offline', 'kind': 'aegis', 'connectionState': 'not_connected'},
            {'endpointId': 'endpoint-1', 'kind': 'aegis', 'connectionState': 'online',
             'profile': {'hostname': 'pixel', 'os': 'linux', 'arch': 'arm64'}},
        ],
        'job': {'key': '#job#com.bank.app#android-device-survey#1', 'status': 'JQ'},
    }


def answer_prompts(monkeypatch, confirms, prompts=None):
    """Feed the TUI's Confirm/Prompt calls, defaulting prompts to the offered default."""
    confirm_answers = list(confirms)

    def confirm(prompt, **kwargs):
        return confirm_answers.pop(0) if confirm_answers else False

    def ask(prompt, **kwargs):
        if prompts:
            for needle, answer in prompts.items():
                if needle in str(prompt):
                    return answer
        return kwargs.get('default', '')

    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Confirm.ask', confirm)
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job.Prompt.ask', ask)
    monkeypatch.setattr('praetorian_cli.ui.aegis.commands.job_helpers.Prompt.ask', ask)


def test_apk_capability_targets_the_apk_asset_not_the_agent_host(monkeypatch):
    """A mobile capability's findings belong to the application, so the job targets it.

    Before this, every non-addomain capability fell through to the selected agent's own
    host asset, which no mobile capability matches.
    """
    menu = Menu(responses=mobile_responses())
    # Use suggested capability, decline large artifact, run the job.
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'android-device-survey'])

    calls = menu.sdk.jobs.calls
    assert len(calls) == 1
    assert calls[0]['target_key'] == '#apk#com.bank.app'
    assert calls[0]['capabilities'] == ['android-device-survey']


def test_apk_job_pins_the_chosen_endpoint(monkeypatch):
    menu = Menu(responses=mobile_responses())
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'android-device-survey'])

    config = json.loads(menu.sdk.jobs.calls[0]['config'])
    assert config['endpoint_agent_id'] == 'endpoint-1'
    # The selected agent is a different inventory from the endpoint, and naming it here
    # would pin the job to a machine that is not the device under test.
    assert 'client_id' not in config


def test_only_connected_endpoints_are_offered(monkeypatch):
    menu = Menu(responses=mobile_responses())
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'android-device-survey'])

    assert menu.sdk.endpoints.calls[0]['online_only'] is True
    config = json.loads(menu.sdk.jobs.calls[0]['config'])
    assert config['endpoint_agent_id'] != 'endpoint-offline'


def test_a_capability_parameter_reaches_the_job_config(monkeypatch):
    """android-device-command declares its command as a parameter, so the existing
    parameter prompt carries it -- the shell command needs no special case."""
    menu = Menu(responses=mobile_responses())
    answer_prompts(monkeypatch, confirms=[True, False, True],
                   prompts={'command': 'getprop ro.build.fingerprint'})

    handle_job(menu, ['run', 'android-device-command'])

    config = json.loads(menu.sdk.jobs.calls[0]['config'])
    assert config['command'] == 'getprop ro.build.fingerprint'
    assert config['endpoint_agent_id'] == 'endpoint-1'


def test_no_apk_uploaded_means_no_job(monkeypatch):
    responses = mobile_responses()
    responses['assets'] = []
    menu = Menu(responses=responses)
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'android-device-survey'])

    assert menu.sdk.jobs.calls == []
    assert any('guard add apk' in line for line in menu.console.lines)


def test_no_online_endpoint_means_no_job(monkeypatch):
    responses = mobile_responses()
    responses['endpoints'] = [
        {'endpointId': 'endpoint-offline', 'kind': 'aegis', 'connectionState': 'not_connected'},
    ]
    menu = Menu(responses=responses)
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'android-device-survey'])

    assert menu.sdk.jobs.calls == []
    assert any('No endpoints are online' in line for line in menu.console.lines)


def test_host_capability_still_targets_the_agent(monkeypatch):
    """The APK branch must not disturb the path every other capability takes."""
    responses = mobile_responses()
    responses['capabilities'] = {
        'linux-enum': {'name': 'linux-enum', 'description': 'Linux enum', 'target': 'asset',
                       'parameters': []},
    }
    menu = Menu(responses=responses)
    answer_prompts(monkeypatch, confirms=[True, False, True])

    handle_job(menu, ['run', 'linux-enum'])

    assert menu.sdk.jobs.calls[0]['target_key'] == '#asset#agent01#agent01'
