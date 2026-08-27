import base64
import json
import os
import time
from datetime import datetime, timezone

import pytest

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.entities.aegis import Aegis
from praetorian_cli.sdk.keychain import DEFAULT_API, DEFAULT_CLIENT_ID, Keychain
from praetorian_cli.sdk.model.aegis import AEGIS_V2_ONLINE_WINDOW_SECONDS, Agent
from praetorian_cli.sdk.test.utils import selected_test_target, setup_chariot


LIVE_AEGIS_V2_ACCOUNT = os.environ.get('CHARIOT_TEST_AEGIS_ACCOUNT', '')
LIVE_AEGIS_V2_ENDPOINT_ID = os.environ.get('CHARIOT_TEST_AEGIS_V2_ENDPOINT_ID', '')
LIVE_AEGIS_PORTSCAN_START_TIMEOUT_SECONDS = int(os.environ.get(
    'CHARIOT_TEST_AEGIS_PORTSCAN_START_TIMEOUT_SECONDS',
    '120',
))
LIVE_AEGIS_PORTSCAN_POLL_INTERVAL_SECONDS = int(os.environ.get(
    'CHARIOT_TEST_AEGIS_PORTSCAN_POLL_INTERVAL_SECONDS',
    '5',
))
LIVE_AEGIS_PORTSCAN_TARGET = os.environ.get('CHARIOT_TEST_AEGIS_PORTSCAN_TARGET', '')


class FakeSearch:
    def __init__(self, endpoints, error=None):
        self.endpoints = endpoints
        self.error = error
        self.calls = []

    def by_key_prefix(self, key_prefix):
        self.calls.append(key_prefix)
        if self.error:
            raise self.error
        return self.endpoints, None


class FakeAPI:
    def __init__(self, agents=None, endpoints=None, endpoint_error=None):
        self.agents = agents or []
        self.search = FakeSearch(endpoints or [], endpoint_error)

    def get(self, path):
        assert path == '/agent/enhanced'
        return self.agents


def test_agent_from_endpoint_dict_maps_aegis_v2_fields():
    last_heartbeat = datetime.now(timezone.utc).isoformat()

    agent = Agent.from_endpoint_dict({
        'key': '#endpoint#endpoint-1',
        'endpointId': 'endpoint-1',
        'kind': 'aegis',
        'version': '1.2.3',
        'hostname': 'sensor-1',
        'os': 'linux',
        'arch': 'amd64',
        'runtime': {'name': 'docker'},
        'cloudflaredStatus': {'hostname': 'sensor.example.com', 'tunnelName': 'sensor-tunnel'},
        'runningContainerCount': 2,
        'lastHeartbeat': last_heartbeat,
    })

    assert agent.version == 'v2'
    assert agent.agent_version == '1.2.3'
    assert agent.endpoint_id == 'endpoint-1'
    assert agent.display_id == 'endpoint-1'
    assert agent.client_id == 'N/A'
    assert agent.hostname == 'sensor-1'
    assert agent.os == 'linux'
    assert agent.architecture == 'amd64'
    assert agent.runtime == {'name': 'docker'}
    assert agent.has_tunnel is True
    assert agent.health_check.cloudflared_status.hostname == 'sensor.example.com'
    assert agent.health_check.cloudflared_status.tunnel_name == 'sensor-tunnel'
    assert agent.running_container_count == 2
    assert agent.is_online is True


def test_agent_from_endpoint_dict_accepts_pascal_fields_and_extended_liveness_window():
    agent = Agent.from_endpoint_dict({
        'Key': '#endpoint#endpoint-1',
        'ID': 'endpoint-1',
        'Kind': 'aegis',
        'Version': '1.2.3',
        'Hostname': 'sensor-1',
        'OS': 'linux',
        'Arch': 'amd64',
        'Runtime': {'name': 'docker'},
        'CloudflaredStatus': {
            'Hostname': 'sensor.example.com',
            'TunnelName': 'sensor-tunnel',
            'AuthorizedUsers': 'alice@example.com',
        },
        'RunningContainerCount': 2,
        'LastHeartbeat': time.time() - (AEGIS_V2_ONLINE_WINDOW_SECONDS - 10),
    })

    assert agent.endpoint_id == 'endpoint-1'
    assert agent.kind == 'aegis'
    assert agent.agent_version == '1.2.3'
    assert agent.has_tunnel is True
    assert agent.health_check.cloudflared_status.hostname == 'sensor.example.com'
    assert agent.health_check.cloudflared_status.tunnel_name == 'sensor-tunnel'
    assert agent.health_check.cloudflared_status.authorized_users == 'alice@example.com'
    assert agent.is_online is True


def test_v2_endpoint_is_offline_after_extended_liveness_window():
    agent = Agent.from_endpoint_dict({
        'endpointId': 'endpoint-1',
        'kind': 'aegis',
        'lastHeartbeat': time.time() - (AEGIS_V2_ONLINE_WINDOW_SECONDS + 10),
    })

    assert agent.is_online is False


def test_legacy_agent_keeps_short_liveness_window():
    agent = Agent.from_dict({
        'client_id': 'C.legacy',
        'hostname': 'legacy',
        'last_seen_at': time.time() - 61,
    })

    assert agent.is_online is False


def test_aegis_list_combines_v1_agents_and_aegis_v2_endpoints():
    api = FakeAPI(
        agents=[{'client_id': 'C.legacy', 'hostname': 'legacy-host'}],
        endpoints=[
            {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
            {'endpointId': 'domitian-1', 'kind': 'domitian', 'hostname': 'other-kind'},
        ],
    )

    agents, offset = Aegis(api).list()

    assert offset is None
    assert api.search.calls == ['#endpoint#']
    assert [(agent.version, agent.hostname, agent.display_id) for agent in agents] == [
        ('v1', 'legacy-host', 'C.legacy'),
        ('v2', 'sensor-1', 'endpoint-1'),
    ]


def test_aegis_list_retains_v1_agents_when_endpoint_listing_fails():
    api = FakeAPI(
        agents=[{'client_id': 'C.legacy', 'hostname': 'legacy-host'}],
        endpoint_error=RuntimeError('endpoint unavailable'),
    )

    agents, offset = Aegis(api).list()

    assert offset is None
    assert [(agent.version, agent.hostname, agent.display_id) for agent in agents] == [
        ('v1', 'legacy-host', 'C.legacy'),
    ]


def test_get_by_client_id_accepts_v2_display_id():
    api = FakeAPI(endpoints=[{'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'}])

    agent = Aegis(api).get_by_client_id('endpoint-1')

    assert agent is not None
    assert agent.version == 'v2'
    assert agent.display_id == 'endpoint-1'


def test_format_agents_list_includes_version_column():
    api = FakeAPI(
        agents=[{'client_id': 'C.legacy', 'hostname': 'legacy-host'}],
        endpoints=[{'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'}],
    )

    output = Aegis(api).format_agents_list()

    assert 'VERSION' in output
    assert 'v1' in output
    assert 'v2' in output
    assert 'C.legacy' in output
    assert 'endpoint-1' in output


def test_format_agents_list_filter_matches_v2_endpoint_id():
    api = FakeAPI(endpoints=[{'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'}])

    output = Aegis(api).format_agents_list(filter_text='endpoint-1')

    assert 'endpoint-1' in output
    assert 'No agents found' not in output


def test_create_job_config_rejects_v2_endpoint_legacy_config():
    agent = Agent.from_endpoint_dict({'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'})

    with pytest.raises(Exception, match='legacy Aegis job path'):
        Aegis(FakeAPI()).create_job_config(agent)


def test_run_job_rejects_v2_endpoint_without_endpoint_agent_id():
    agent = Agent.from_endpoint_dict({'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'})

    with pytest.raises(Exception, match='endpoint_agent_id'):
        Aegis(FakeAPI()).run_job(agent, ['portscan'], '{}')


def _selected_live_target_or_skip():
    try:
        return selected_test_target()
    except ValueError as exc:
        pytest.skip(str(exc))


def _setup_live_chariot(profile: str, account: str) -> Chariot:
    api_key_id = os.environ.get('PRAETORIAN_CLI_API_KEY_ID')
    api_key_secret = os.environ.get('PRAETORIAN_CLI_API_KEY_SECRET')
    if api_key_id and api_key_secret:
        keychain_data = (
            f'[{profile}]\n'
            f'api = {os.environ.get("PRAETORIAN_CLI_API", DEFAULT_API)}\n'
            f'client_id = {os.environ.get("PRAETORIAN_CLI_CLIENT_ID", DEFAULT_CLIENT_ID)}\n'
            f'api_key_id = {api_key_id}\n'
            f'api_key_secret = {api_key_secret}\n'
        )
        return Chariot(Keychain(profile=profile, account=account, data=keychain_data))
    return setup_chariot(profile, account)


def _setup_endpoint_fixture_chariot_or_skip() -> Chariot:
    if not LIVE_AEGIS_V2_ACCOUNT:
        pytest.skip('set CHARIOT_TEST_AEGIS_ACCOUNT to the account that owns the live endpoint fixture')
    profile, account = _selected_live_target_or_skip()
    if account.lower() != LIVE_AEGIS_V2_ACCOUNT.lower():
        pytest.skip('selected account does not own the live Aegis v2 endpoint fixture')
    return _setup_live_chariot(profile, account)


def _find_known_live_v2_endpoint(sdk: Chariot):
    agents, offset = sdk.aegis.list()
    endpoint = next(
        (agent for agent in agents if getattr(agent, 'endpoint_id', None) == LIVE_AEGIS_V2_ENDPOINT_ID),
        None,
    )
    return endpoint, agents, offset


def _endpoint_task_key(endpoint_id: str, task_id: str) -> str:
    encoded_endpoint_id = base64.urlsafe_b64encode(endpoint_id.encode()).decode().rstrip('=')
    return f'#endpointtask#{encoded_endpoint_id}#{task_id}'


def _existing_portscan_asset_key_or_skip(sdk: Chariot) -> str:
    if not LIVE_AEGIS_PORTSCAN_TARGET:
        pytest.skip('set CHARIOT_TEST_AEGIS_PORTSCAN_TARGET to an existing asset key or IP/CIDR asset')
    asset_key = LIVE_AEGIS_PORTSCAN_TARGET
    if not asset_key.startswith('#'):
        asset_key = f'#asset#{LIVE_AEGIS_PORTSCAN_TARGET}#{LIVE_AEGIS_PORTSCAN_TARGET}'
    asset = sdk.assets.get(asset_key)
    if not asset:
        pytest.skip(f'live Aegis v2 portscan target asset is missing: {asset_key}')
    return asset.get('key') or asset_key


def _job_state(job: dict) -> str:
    return (job.get('status') or '').split('#', 1)[0]


def _wait_for_endpoint_bound_job(sdk: Chariot, job_key: str) -> dict:
    deadline = time.time() + LIVE_AEGIS_PORTSCAN_START_TIMEOUT_SECONDS
    last_job = None
    while time.time() < deadline:
        last_job = sdk.jobs.get(job_key)
        if last_job and last_job.get('endpoint_task_id'):
            return last_job
        time.sleep(LIVE_AEGIS_PORTSCAN_POLL_INTERVAL_SECONDS)
    pytest.fail(f'expected endpoint-bound portscan job {job_key}; last job: {last_job!r}')


def _wait_for_endpoint_task(sdk: Chariot, endpoint_id: str, task_id: str) -> dict:
    task_key = _endpoint_task_key(endpoint_id, task_id)
    deadline = time.time() + LIVE_AEGIS_PORTSCAN_START_TIMEOUT_SECONDS
    last_task = None
    while time.time() < deadline:
        last_task = sdk.search.by_exact_key(task_key)
        if last_task:
            return last_task
        time.sleep(LIVE_AEGIS_PORTSCAN_POLL_INTERVAL_SECONDS)
    pytest.fail(f'expected endpoint task {task_key}; last task: {last_task!r}')


def _wait_for_endpoint_job_to_start(sdk: Chariot, job_key: str) -> dict:
    deadline = time.time() + LIVE_AEGIS_PORTSCAN_START_TIMEOUT_SECONDS
    last_job = None
    while time.time() < deadline:
        last_job = sdk.jobs.get(job_key)
        if last_job and _job_state(last_job) in {'JR', 'JP', 'JF'}:
            return last_job
        time.sleep(LIVE_AEGIS_PORTSCAN_POLL_INTERVAL_SECONDS)
    pytest.fail(f'expected endpoint portscan job {job_key} to start; last job: {last_job!r}')


@pytest.mark.coherence
def test_live_aegis_list_includes_known_v2_endpoint():
    sdk = _setup_endpoint_fixture_chariot_or_skip()

    endpoint, agents, offset = _find_known_live_v2_endpoint(sdk)

    assert offset is None
    assert endpoint is not None, f'expected Aegis v2 endpoint {LIVE_AEGIS_V2_ENDPOINT_ID} in live list'
    assert endpoint.version == 'v2'
    assert endpoint.display_id == LIVE_AEGIS_V2_ENDPOINT_ID
    assert endpoint.client_id == 'N/A'
    assert endpoint.is_online is True
    assert any(agent.version == 'v1' for agent in agents)

    output = sdk.aegis.format_agents_list()
    assert 'VERSION' in output
    assert 'v2' in output
    assert LIVE_AEGIS_V2_ENDPOINT_ID in output


@pytest.mark.coherence
def test_live_aegis_v2_portscan_runs_existing_asset_on_known_endpoint():
    sdk = _setup_endpoint_fixture_chariot_or_skip()

    endpoint, _, _ = _find_known_live_v2_endpoint(sdk)
    assert endpoint is not None, f'expected Aegis v2 endpoint {LIVE_AEGIS_V2_ENDPOINT_ID} in live list'
    assert endpoint.is_online is True

    asset_key = _existing_portscan_asset_key_or_skip(sdk)
    jobs = sdk.jobs.add(
        asset_key,
        ['portscan'],
        json.dumps({'endpoint_agent_id': endpoint.endpoint_id}),
    )
    assert len(jobs) == 1
    created_job = jobs[0]
    assert created_job['key'].startswith('#job#')
    assert created_job.get('config', {}).get('endpoint_agent_id') == endpoint.endpoint_id

    bound_job = _wait_for_endpoint_bound_job(sdk, created_job['key'])
    task_id = bound_job.get('endpoint_task_id')
    assert task_id
    assert bound_job.get('config', {}).get('endpoint_agent_id') == endpoint.endpoint_id

    task = _wait_for_endpoint_task(sdk, endpoint.endpoint_id, task_id)
    assert task['endpointId'] == endpoint.endpoint_id
    assert task['taskId'] == task_id
    assert task['jobKey'] == created_job['key']

    started_job = _wait_for_endpoint_job_to_start(sdk, created_job['key'])
    assert _job_state(started_job) in {'JR', 'JP', 'JF'}
