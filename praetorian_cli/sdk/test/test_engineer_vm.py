"""
Unit tests for the Engineer VM CLI surface. These are self-contained — no live
backend — so they run with a bare `pytest praetorian_cli/sdk/test/test_engineer_vm.py`.

They lock down two things that are easy to get wrong: the exact REST routes/bodies
each SDK method hits, and the gateway URL construction the ssh/code-server flows
depend on.
"""

from praetorian_cli.handlers.vm import format_vm_table, proxy_nesting
from praetorian_cli.handlers.vm_proxy import build_code_server_url, build_connect_url
from praetorian_cli.sdk.entities.engineer_vm import EngineerVms
from praetorian_cli.sdk.model.vm import (
    TIERS, is_running, is_snapshotted, is_stopped,
    STATUS_PROVISIONING, STATUS_SNAPSHOTTED, STATUS_STOPPED,
    status_label,
)


class FakeApi:
    """ Records the (method, type, body, params) of every call the entity makes. """

    def __init__(self, get_result=None, post_result=None):
        self.calls = []
        self._get_result = get_result if get_result is not None else {'engineer_vms': []}
        self._post_result = post_result if post_result is not None else {'ok': True}

    def get(self, type, params=None):
        self.calls.append(('GET', type, None, params))
        return self._get_result

    def post(self, type, body, params=None):
        self.calls.append(('POST', type, body, params))
        return self._post_result

    def delete(self, type, body, params):
        self.calls.append(('DELETE', type, body, params))
        return {'ok': True}


def test_list_hits_collection_route_and_unwraps():
    api = FakeApi(get_result={'engineer_vms': [{'vm_id': 'v1'}]})
    vms = EngineerVms(api).list()
    assert vms == [{'vm_id': 'v1'}]
    assert api.calls == [('GET', 'engineer-vm', None, None)]


def test_list_tolerates_missing_key():
    assert EngineerVms(FakeApi(get_result={})).list() == []


def test_get_hits_item_route():
    api = FakeApi(get_result={'vm_id': 'v1'})
    EngineerVms(api).get('v1')
    assert api.calls == [('GET', 'engineer-vm/v1', None, None)]


def test_launch_posts_tier():
    api = FakeApi()
    EngineerVms(api).launch(tier='heavy')
    method, type_, body, _ = api.calls[0]
    assert (method, type_) == ('POST', 'engineer-vm')
    assert body == {'tier': 'heavy'}


def test_launch_includes_restore_snapshot_only_when_set():
    api = FakeApi()
    EngineerVms(api).launch(restore_snapshot_id='snap-1')
    assert api.calls[0][2]['restore_snapshot_id'] == 'snap-1'
    assert api.calls[0][2].get('tier') == 'light'

    api2 = FakeApi()
    EngineerVms(api2).launch()
    assert 'restore_snapshot_id' not in api2.calls[0][2]
    assert api2.calls[0][2] == {'tier': 'light'}


def test_action_routes():
    api = FakeApi()
    e = EngineerVms(api)
    e.pause('v1')
    e.resume('v1')
    e.archive('v1')
    e.revive('v1')
    assert api.calls[0] == ('POST', 'engineer-vm/v1/pause', {}, None)
    assert api.calls[1] == ('POST', 'engineer-vm/v1/resume', {}, None)
    assert api.calls[2] == ('DELETE', 'engineer-vm/v1', {}, {})
    assert api.calls[3] == ('POST', 'engineer-vm/v1/restore', {}, None)


def test_extend_omits_body_without_hours_and_includes_it_with():
    api = FakeApi()
    EngineerVms(api).extend('v1')
    assert api.calls[0] == ('POST', 'engineer-vm/v1/extend', {}, None)

    api2 = FakeApi()
    EngineerVms(api2).extend('v1', hours=24)
    assert api2.calls[0][2] == {'hours': 24}


def test_ssh_cert_sends_only_public_key():
    api = FakeApi(post_result={'certificate': 'C', 'gateway_url': 'gw'})
    EngineerVms(api).ssh_cert('v1', 'ssh-ed25519 AAAA')
    method, type_, body, _ = api.calls[0]
    assert (method, type_) == ('POST', 'engineer-vm/v1/ssh-cert')
    assert body == {'public_key': 'ssh-ed25519 AAAA'}


def test_code_server_token_route():
    api = FakeApi(post_result={'token': 'T', 'gateway_url': 'gw'})
    EngineerVms(api).code_server_token('v1')
    assert api.calls[0] == ('POST', 'engineer-vm/v1/code-server-token', {}, None)


# --- URL construction --------------------------------------------------------

def test_connect_url_defaults_bare_host_to_wss():
    url = build_connect_url('gw-host.example.com', 'tok', 'v1', 'ssh', 'acme')
    assert url.startswith('wss://gw-host.example.com/connect?')
    assert 'token=tok' in url
    assert 'vm_id=v1' in url
    assert 'target=ssh' in url
    assert 'account=acme' in url


def test_connect_url_rewrites_https_to_wss_and_omits_empty_account():
    url = build_connect_url('https://gw/', 'tok', 'v1', 'ssh')
    assert url.startswith('wss://gw/connect?')
    assert 'account=' not in url


def test_code_server_url_normalizes_scheme():
    assert build_code_server_url('gw-host', 'tok').startswith('https://gw-host/code-server/?token=tok')
    assert build_code_server_url('wss://gw', 'tok').startswith('https://gw/code-server/?token=tok')


# --- model helpers -----------------------------------------------------------

def test_status_label_strips_prefix():
    assert status_label('EV#running') == 'running'
    assert status_label('running') == 'running'
    assert status_label('') == ''


def test_is_running():
    assert is_running({'status': 'EV#running'})
    assert not is_running({'status': 'EV#paused'})
    assert not is_running({})


def test_is_stopped_and_is_snapshotted():
    assert is_stopped({'status': 'EV#stopped'})
    assert is_stopped({'status': 'EV#paused'})
    assert not is_stopped({})
    assert not is_stopped({'status': 'EV#running'})

    assert is_snapshotted({'status': 'EV#snapshotted'})
    assert is_snapshotted({'status': 'EV#snapshot_retained'})
    assert not is_snapshotted({})
    assert not is_snapshotted({'status': 'EV#stopped'})


def test_constants_match_backend():
    assert TIERS == ('light', 'general', 'heavy')
    assert STATUS_PROVISIONING == 'EV#provisioning'
    assert STATUS_STOPPED == 'EV#stopped'
    assert STATUS_SNAPSHOTTED == 'EV#snapshotted'


def test_proxy_nesting_matches_entry_point():
    # The ssh ProxyCommand re-invokes the CLI; `praetorian` nests vm under the
    # chariot group, `guard` exposes it flat. Getting this wrong breaks ssh.
    assert proxy_nesting('praetorian') == ['chariot', 'vm']
    assert proxy_nesting('guard') == ['vm']
    assert proxy_nesting('guard-cli') == ['vm']


def test_format_vm_table_empty_and_rows():
    assert format_vm_table([]) == 'No engineer VMs.'
    table = format_vm_table([
        {'vm_id': 'v1', 'status': 'EV#running', 'tier': 'light',
         'private_ip': '10.0.0.1', 'expiry_at': 0},
    ])
    assert 'VM ID' in table and 'v1' in table
    assert 'MODE' not in table

    # phase present -> table shows the derived phase, not status_label
    table_with_phase = format_vm_table([
        {'vm_id': 'v2', 'phase': 'provisioning', 'status': 'EV#running',
         'tier': 'light', 'private_ip': '10.0.0.2', 'expiry_at': 0},
    ])
    assert 'provisioning' in table_with_phase
    assert 'running' not in table_with_phase.split('\n')[1]  # data row shows phase not status_label

    # no phase -> falls back to status_label
    table_no_phase = format_vm_table([
        {'vm_id': 'v3', 'status': 'EV#running', 'tier': 'light',
         'private_ip': '10.0.0.3', 'expiry_at': 0},
    ])
    assert 'running' in table_no_phase
