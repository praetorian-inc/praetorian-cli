"""CLI-level contract for `guard aegis job`.

The SDK guards -- one target only, no unpinned v2 execution -- are only worth having if
the command cannot route around them. These tests drive the Click command itself with a
fake SDK and assert two things for every refusal: a non-zero exit, and that nothing
reached jobs.add().
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import praetorian_cli.handlers.aegis  # noqa: F401 - registers aegis commands on chariot
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.model.aegis import Agent
from praetorian_cli.sdk.test.test_mobile_dispatch import FakeApi, FakeJobs, SURVEY

V1_CLIENT_ID = 'C.6e012b467f9faf82-OG9F0'
V2_CLIENT_ID = 'C.pixel-v2'
ENDPOINT_ID = 'endpoint-1'


def agent(client_id, version='v1', endpoint_id=None):
    return Agent(client_id=client_id, hostname='pixel' if version == 'v2' else 'agent01',
                 version=version, endpoint_id=endpoint_id)


class FakeSDK:
    def __init__(self, agents=(), api=None):
        self.api = api or FakeApi()
        self.aegis = Aegis(self.api)
        self._agents = {a.client_id: a for a in agents}
        self.aegis.get_by_client_id = lambda client_id: self._agents.get(client_id)

    @property
    def submitted(self):
        return self.api.jobs.calls


def invoke(sdk, argv):
    obj = {'keychain': MagicMock(), 'proxy': ''}
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda function: function):
        return CliRunner().invoke(chariot, ['aegis', 'job'] + argv, obj=obj)


class TestTargetSelection:

    def test_no_target_exits_nonzero_and_submits_nothing(self):
        sdk = FakeSDK()

        result = invoke(sdk, ['-c', SURVEY])

        assert result.exit_code != 0
        assert 'No target' in result.output
        assert sdk.submitted == []

    def test_two_targets_exit_nonzero_and_submit_nothing(self):
        sdk = FakeSDK(agents=[agent(V1_CLIENT_ID)])

        result = invoke(sdk, [V1_CLIENT_ID, '--package', 'com.bank.app', '-c', SURVEY])

        assert result.exit_code != 0
        assert 'one target' in result.output
        assert sdk.submitted == []

    def test_unknown_agent_exits_nonzero(self):
        sdk = FakeSDK()

        result = invoke(sdk, ['C.nobody', '-c', 'linux-enum'])

        assert result.exit_code != 0
        assert 'Agent not found' in result.output
        assert sdk.submitted == []


class TestV2Guard:

    def test_a_v2_client_id_cannot_reach_jobs_add(self):
        # The one that matters: main refuses this, and a handler that forwarded only the
        # hostname would submit it against #asset#pixel#pixel with no endpoint pin.
        sdk = FakeSDK(agents=[agent(V2_CLIENT_ID, version='v2', endpoint_id=ENDPOINT_ID)])

        result = invoke(sdk, [V2_CLIENT_ID, '-c', SURVEY])

        assert result.exit_code != 0
        assert 'v2 endpoint' in result.output
        assert ENDPOINT_ID in result.output, 'the refusal names the pin to use instead'
        assert sdk.submitted == []

    def test_a_v2_client_id_is_refused_even_with_an_endpoint_pin(self):
        sdk = FakeSDK(agents=[agent(V2_CLIENT_ID, version='v2', endpoint_id=ENDPOINT_ID)])

        result = invoke(sdk, [V2_CLIENT_ID, '-c', SURVEY, '-e', ENDPOINT_ID])

        assert result.exit_code != 0
        assert sdk.submitted == []


class TestDispatch:

    def test_a_v1_agent_still_runs_against_its_host(self):
        sdk = FakeSDK(agents=[agent(V1_CLIENT_ID)],
                      api=FakeApi(jobs=FakeJobs({'key': '#job#agent01#linux-enum', 'status': 'JQ'})))

        result = invoke(sdk, [V1_CLIENT_ID, '-c', 'linux-enum'])

        assert result.exit_code == 0, result.output
        assert [call['target_key'] for call in sdk.submitted] == ['#asset#agent01#agent01']
        assert 'Job queued' in result.output

    def test_a_package_dispatches_to_the_pinned_endpoint(self):
        sdk = FakeSDK()

        result = invoke(sdk, ['--package', 'com.bank.app', '-c', SURVEY, '-e', ENDPOINT_ID])

        assert result.exit_code == 0, result.output
        assert [call['target_key'] for call in sdk.submitted] == ['#apk#com.bank.app']
        assert f'Endpoint: {ENDPOINT_ID}' in result.output
