"""Unit tests for dispatching mobile capabilities from the SDK.

These exercise sdk.aegis.run_job and sdk.apks.add against fakes rather than a backend,
so they assert the shapes the CLI and the MCP server both depend on: the target key a
mobile job carries, the endpoint pin, and the errors a caller sees before a job is
created rather than after.
"""

import json

import pytest

from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.entities.apks import Apks

SURVEY = 'android-device-survey'
ONLINE_ENDPOINT = {
    'endpointId': 'endpoint-1',
    'kind': 'aegis',
    'connectionState': 'online',
    'profile': {'hostname': 'pixel', 'os': 'linux', 'arch': 'arm64'},
}


class FakeJobs:
    def __init__(self, job=None):
        self.calls = []
        self._job = job if job is not None else {'key': '#job#com.bank.app#' + SURVEY, 'status': 'JQ'}

    def add(self, target_key, capabilities, config=None, credentials=None):
        self.calls.append({'target_key': target_key, 'capabilities': capabilities, 'config': config})
        return [self._job] if self._job else []


class FakeEndpoints:
    def __init__(self, endpoints=None):
        self._endpoints = endpoints if endpoints is not None else [ONLINE_ENDPOINT]

    def get(self, endpoint_id):
        for endpoint in self._endpoints:
            if endpoint.get('endpointId') == endpoint_id:
                return endpoint
        return None


class FakeCapabilities:
    def __init__(self, capabilities=None):
        self.calls = []
        self._capabilities = capabilities if capabilities is not None else []

    def list(self, name='', target='', executor='', endpoint_kind=''):
        self.calls.append({'name': name, 'target': target, 'executor': executor,
                           'endpoint_kind': endpoint_kind})
        return self._capabilities


class FakeApi:
    """Stands in for the Chariot instance an entity is constructed with."""

    def __init__(self, jobs=None, endpoints=None, capabilities=None):
        self.jobs = jobs or FakeJobs()
        self.endpoints = endpoints or FakeEndpoints()
        self.capabilities = capabilities or FakeCapabilities()
        self.uploads = []
        self.posts = []

    def upload(self, local_filepath, chariot_filepath=None, praetorian=False):
        self.uploads.append((local_filepath, chariot_filepath))
        return {}

    def post(self, type, body, params=None):
        self.posts.append((type, body))
        return {'key': '#apk#com.bank.app', 'package': 'com.bank.app', 'versionName': '1.2.3'}


class TestRunJobTarget:

    def test_package_targets_the_apk_asset(self):
        api = FakeApi()
        result = Aegis(api).run_job(capabilities=[SURVEY], package='com.bank.app',
                                    endpoint_id='endpoint-1')

        assert api.jobs.calls[0]['target_key'] == '#apk#com.bank.app'
        assert result['target_key'] == '#apk#com.bank.app'
        assert result['endpoint_id'] == 'endpoint-1'
        assert result['success'] is True

    def test_hostname_still_targets_the_agent_host_asset(self):
        api = FakeApi()
        Aegis(api).run_job(capabilities=['linux-enum'], hostname='agent01')

        assert api.jobs.calls[0]['target_key'] == '#asset#agent01#agent01'

    def test_no_target_is_refused(self):
        with pytest.raises(Exception) as e:
            Aegis(FakeApi()).run_job(capabilities=[SURVEY])
        assert 'No target' in str(e.value)

    def test_an_agent_passed_positionally_is_reported_as_a_call_error(self):
        # The old signature took an Agent first. A caller who has not migrated should be
        # told about the call, not about the target.
        class Agentish:
            hostname = 'agent01'

        with pytest.raises(Exception) as e:
            Aegis(FakeApi()).run_job(Agentish())
        assert 'capabilities must be a list' in str(e.value)

    def test_two_targets_are_refused(self):
        with pytest.raises(Exception) as e:
            Aegis(FakeApi()).run_job(capabilities=[SURVEY], hostname='agent01', package='com.bank.app')
        assert 'one target' in str(e.value)


class TestEndpointPin:

    def test_endpoint_is_pinned_in_the_job_config(self):
        api = FakeApi()
        Aegis(api).run_job(capabilities=[SURVEY], package='com.bank.app', endpoint_id='endpoint-1')

        config = json.loads(api.jobs.calls[0]['config'])
        assert config['endpoint_agent_id'] == 'endpoint-1'

    def test_caller_config_survives_the_pin(self):
        api = FakeApi()
        Aegis(api).run_job(capabilities=['android-device-command'], package='com.bank.app',
                           endpoint_id='endpoint-1', config='{"command": "id"}')

        config = json.loads(api.jobs.calls[0]['config'])
        assert config == {'command': 'id', 'endpoint_agent_id': 'endpoint-1'}

    def test_no_endpoint_leaves_the_config_alone(self):
        api = FakeApi()
        Aegis(api).run_job(capabilities=['linux-enum'], hostname='agent01')

        assert api.jobs.calls[0]['config'] is None

    def test_unenrolled_endpoint_fails_before_the_job_is_created(self):
        api = FakeApi(endpoints=FakeEndpoints([]))
        with pytest.raises(Exception) as e:
            Aegis(api).run_job(capabilities=[SURVEY], package='com.bank.app', endpoint_id='endpoint-1')

        assert 'not enrolled' in str(e.value)
        assert api.jobs.calls == []

    def test_offline_endpoint_fails_before_the_job_is_created(self):
        offline = dict(ONLINE_ENDPOINT, connectionState='not_connected')
        api = FakeApi(endpoints=FakeEndpoints([offline]))
        with pytest.raises(Exception) as e:
            Aegis(api).run_job(capabilities=[SURVEY], package='com.bank.app', endpoint_id='endpoint-1')

        assert 'not_connected' in str(e.value)
        assert api.jobs.calls == []

    def test_paused_endpoint_fails_before_the_job_is_created(self):
        paused = dict(ONLINE_ENDPOINT, taskDispatchPaused=True)
        api = FakeApi(endpoints=FakeEndpoints([paused]))
        with pytest.raises(Exception) as e:
            Aegis(api).run_job(capabilities=[SURVEY], package='com.bank.app', endpoint_id='endpoint-1')

        assert 'paused' in str(e.value)
        assert api.jobs.calls == []

    def test_invalid_config_json_is_reported_as_such(self):
        with pytest.raises(Exception) as e:
            Aegis(FakeApi()).run_job(capabilities=[SURVEY], package='com.bank.app',
                                     config='{"command": "id"')
        assert 'not valid JSON' in str(e.value)

    def test_config_must_be_an_object(self):
        with pytest.raises(Exception) as e:
            Aegis(FakeApi()).run_job(capabilities=[SURVEY], package='com.bank.app',
                                     config='["id"]')
        assert 'JSON object' in str(e.value)


class TestCapabilityOffering:

    def test_an_apk_target_offers_endpoint_dispatchable_apk_capabilities(self):
        capabilities = FakeCapabilities([{'name': SURVEY, 'target': ['apk'], 'surface': 'mobile'}])
        result = Aegis(FakeApi(capabilities=capabilities)).run_job(package='com.bank.app')

        assert [c['name'] for c in result['capabilities']] == [SURVEY]
        assert capabilities.calls[0]['target'] == 'apk'
        assert capabilities.calls[0]['endpoint_kind'] == 'aegis'
        # The agent executor would exclude every mobile capability.
        assert capabilities.calls[0]['executor'] == ''

    def test_an_agent_target_still_offers_internal_host_capabilities(self):
        capabilities = FakeCapabilities([{'name': 'linux-enum', 'surface': 'internal'}])
        result = Aegis(FakeApi(capabilities=capabilities)).run_job(hostname='agent01')

        assert [c['name'] for c in result['capabilities']] == ['linux-enum']
        assert capabilities.calls[0]['executor'] == 'aegis'
        assert capabilities.calls[0]['endpoint_kind'] == ''

    def test_offered_capabilities_are_sorted_by_name(self):
        capabilities = FakeCapabilities([
            {'name': 'android-traffic-capture', 'surface': 'mobile'},
            {'name': SURVEY, 'surface': 'mobile'},
        ])
        result = Aegis(FakeApi(capabilities=capabilities)).run_job(package='com.bank.app')

        assert [c['name'] for c in result['capabilities']] == [SURVEY, 'android-traffic-capture']


class TestApkUpload:

    def test_upload_then_register(self, tmp_path):
        apk_file = tmp_path / 'bank-app.apk'
        apk_file.write_bytes(b'PK\x03\x04')
        api = FakeApi()

        result = Apks(api).add(str(apk_file))

        assert api.uploads == [(str(apk_file), 'bank-app.apk')]
        assert api.posts == [('apk', {'artifact_key': 'bank-app.apk'})]
        assert result['key'] == '#apk#com.bank.app'

    def test_explicit_storage_path_is_used(self, tmp_path):
        apk_file = tmp_path / 'bank-app.apk'
        apk_file.write_bytes(b'PK\x03\x04')
        api = FakeApi()

        Apks(api).add(str(apk_file), 'engagements/acme/bank-app.apk')

        assert api.posts == [('apk', {'artifact_key': 'engagements/acme/bank-app.apk'})]

    def test_a_missing_file_is_refused_without_uploading(self, tmp_path):
        api = FakeApi()
        with pytest.raises(Exception) as e:
            Apks(api).add(str(tmp_path / 'absent.apk'))

        assert 'not found' in str(e.value)
        assert api.uploads == []

    def test_a_non_apk_storage_path_is_refused_before_the_upload(self, tmp_path):
        # POST /apk rejects this too, but only after the transfer has been paid for.
        other = tmp_path / 'notes.txt'
        other.write_text('hello')
        api = FakeApi()

        with pytest.raises(Exception) as e:
            Apks(api).add(str(other))

        assert 'must end in .apk' in str(e.value)
        assert api.uploads == []
