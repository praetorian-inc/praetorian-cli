"""Tests for account discovery with aegis agent filtering."""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def _active_subscription():
    """Build a subscription window that is always active relative to now."""
    today = datetime.now().date()
    return {
        'startDate': (today - timedelta(days=30)).isoformat(),
        'endDate': (today + timedelta(days=365)).isoformat(),
    }


def _expired_subscription():
    """Build a subscription window that is always expired relative to now."""
    today = datetime.now().date()
    return {
        'startDate': (today - timedelta(days=365)).isoformat(),
        'endDate': (today - timedelta(days=30)).isoformat(),
    }


def _make_sdk(accounts, agents_by_account=None):
    """Build a mock SDK that returns given accounts and per-account agents."""
    sdk = MagicMock()

    sdk.accounts.list.return_value = (accounts, None)
    sdk.accounts.current_principal.return_value = 'operator@praetorian.com'
    sdk.accounts.login_principal.return_value = 'operator@praetorian.com'

    agents_by_account = agents_by_account or {}

    # For concurrent discovery: keychain.base_url() and keychain.headers()
    sdk.keychain.base_url.return_value = 'https://api.example.com'
    sdk.keychain.headers.return_value = {'Authorization': 'Bearer test-token'}

    # Wire assume_role/unassume_role for load_agents/load_schedules (sequential paths)
    sdk.keychain.account = None

    def mock_assume_role(email):
        sdk.keychain.account = email
    sdk.accounts.assume_role.side_effect = mock_assume_role

    def mock_unassume_role():
        sdk.keychain.account = None
    sdk.accounts.unassume_role.side_effect = mock_unassume_role

    def mock_aegis_list():
        current_account = sdk.keychain.account
        agents = agents_by_account.get(current_account, [])
        return (agents, None)

    sdk.aegis.list.side_effect = mock_aegis_list
    return sdk


def _make_agent(hostname='host1'):
    """Create a minimal mock Agent."""
    agent = MagicMock()
    agent.hostname = hostname
    agent.client_id = f'C.{hostname}'
    return agent


def _account(name, member='operator@praetorian.com', config=None):
    """Create an account dict matching Chariot entity shape."""
    return {
        'name': name,
        'member': member,
        'key': f'#account#{name}#{member}',
        'status': 'A',
        'dns': name,
        'config': config or {},
    }


def _mock_requests_get(agents_by_account, metadata=None, endpoints_by_account=None):
    """Create a mock for requests.get that simulates API endpoints.

    metadata keys: types, subscriptions, frozen, display_names
    Each maps email -> value for allTenants bulk responses.
    """
    metadata = metadata or {}
    endpoints_by_account = endpoints_by_account or {}
    types = metadata.get('types', {})
    subscriptions = metadata.get('subscriptions', {})
    frozen = metadata.get('frozen', {})
    display_names = metadata.get('display_names', {})

    def mock_get(url, headers=None, params=None, timeout=None):
        account_email = (headers or {}).get('account', '')
        resp = MagicMock()
        params = params or {}

        if '/agent/enhanced' in url:
            agents = agents_by_account.get(account_email, [])
            agent_dicts = [{'hostname': a.hostname, 'client_id': a.client_id} for a in agents]
            resp.status_code = 200
            resp.json.return_value = agent_dicts
        elif '/my' in url and params.get('allTenants') == 'true':
            key = params.get('key', '')
            records = []
            if '#configuration#' in key:
                # Configurations: customer_type + subscription
                for email, ctype in types.items():
                    records.append({'username': email, 'name': 'customer_type', 'value': ctype})
                for email, sub in subscriptions.items():
                    records.append({'username': email, 'name': 'subscription', 'value': sub})
            elif '#setting#' in key:
                # Settings: frozen + display-name
                for email, is_frozen in frozen.items():
                    records.append({'username': email, 'name': 'frozen', 'value': 'true' if is_frozen else 'false'})
                for email, dname in display_names.items():
                    records.append({'username': email, 'name': 'display-name', 'value': dname})
            resp.status_code = 200
            resp.json.return_value = {'configurations': records}
        elif url.endswith('/endpoint/list'):
            resp.status_code = 200
            resp.json.return_value = {
                'endpoints': endpoints_by_account.get(account_email, [])
            }
        elif url.endswith('/endpoint'):
            resp.status_code = 200
            resp.json.return_value = endpoints_by_account.get(account_email, [])
        elif '/my' in url and params.get('key') == '#endpoint#':
            resp.status_code = 200
            resp.json.return_value = {'endpoints': endpoints_by_account.get(account_email, [])}
        else:
            resp.status_code = 404
            resp.json.return_value = {}

        return resp
    return mock_get


class TestDiscoverAegisAccounts:
    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_returns_only_accounts_with_agents(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [
            _account('acme@praetorian.com'),
            _account('empty@praetorian.com'),
        ]
        agents_map = {
            'acme@praetorian.com': [_make_agent('server1')],
            'empty@praetorian.com': [],  # no agents
        }
        metadata = {
            'types': {'acme@praetorian.com': 'MANAGED', 'empty@praetorian.com': 'PILOT'},
            'display_names': {'acme@praetorian.com': 'Acme Corp', 'empty@praetorian.com': 'Empty Inc'},
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, metadata)
        result = discover_aegis_accounts(sdk)

        assert len(result) == 1
        assert result[0]['account_email'] == 'acme@praetorian.com'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_returns_accounts_with_v2_endpoints(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [
            _account('endpoint@praetorian.com'),
            _account('empty@praetorian.com'),
        ]
        agents_map = {'endpoint@praetorian.com': [], 'empty@praetorian.com': []}
        endpoints_map = {
            'endpoint@praetorian.com': [
                {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
            ],
            'empty@praetorian.com': [],
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, {}, endpoints_map)

        result = discover_aegis_accounts(sdk)

        assert len(result) == 1
        assert result[0]['account_email'] == 'endpoint@praetorian.com'
        assert result[0]['agent_count'] == 1

    def test_retries_transient_endpoint_failure_before_marking_account_empty(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('endpoint@praetorian.com')]
        sdk = _make_sdk(accounts, {'endpoint@praetorian.com': []})
        calls = {'endpoint': 0}

        def mock_get(url, headers=None, params=None, timeout=None):
            params = params or {}
            resp = MagicMock()
            if '/agent/enhanced' in url:
                resp.status_code = 200
                resp.json.return_value = []
            elif '/my' in url and params.get('allTenants') == 'true':
                resp.status_code = 200
                resp.json.return_value = {}
            elif '/my' in url and params.get('key') == '#endpoint#':
                calls['endpoint'] += 1
                resp.status_code = 503 if calls['endpoint'] == 1 else 200
                resp.json.return_value = {'endpoints': [
                    {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
                ]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.time.sleep', lambda _seconds: None)

        result = discover_aegis_accounts(sdk)

        assert calls['endpoint'] == 2
        assert len(result) == 1
        assert result[0]['account_email'] == 'endpoint@praetorian.com'
        assert result[0]['agent_count'] == 1

    def test_retries_repeated_endpoint_cursor_before_marking_account_empty(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('endpoint@praetorian.com')]
        sdk = _make_sdk(accounts, {'endpoint@praetorian.com': []})
        calls = {'endpoint': 0}
        repeated_offset = {'cursor': 'same'}

        def mock_get(url, headers=None, params=None, timeout=None):
            params = params or {}
            resp = MagicMock()
            if '/agent/enhanced' in url:
                resp.status_code = 200
                resp.json.return_value = []
            elif '/my' in url and params.get('allTenants') == 'true':
                resp.status_code = 200
                resp.json.return_value = {}
            elif '/my' in url and params.get('key') == '#endpoint#':
                calls['endpoint'] += 1
                resp.status_code = 200
                if calls['endpoint'] <= 2:
                    resp.json.return_value = {'endpoints': [], 'offset': repeated_offset}
                else:
                    resp.json.return_value = {'endpoints': [
                        {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
                    ]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.time.sleep', lambda _seconds: None)

        result = discover_aegis_accounts(sdk)

        assert calls['endpoint'] == 3
        assert len(result) == 1
        assert result[0]['account_email'] == 'endpoint@praetorian.com'
        assert result[0]['agent_count'] == 1

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_account_metadata_extraction(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('client@praetorian.com')]
        agents_map = {'client@praetorian.com': [_make_agent()]}
        metadata = {
            'types': {'client@praetorian.com': 'MANAGED'},
            'display_names': {'client@praetorian.com': 'Cushman & Wakefield'},
            'subscriptions': {'client@praetorian.com': _active_subscription()},
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, metadata)
        result = discover_aegis_accounts(sdk)

        assert result[0]['display_name'] == 'Cushman & Wakefield'
        assert result[0]['status'] == 'Active'
        assert result[0]['account_type'] == 'MANAGED'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_fallback_display_name_to_email(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('noname@praetorian.com')]
        agents_map = {'noname@praetorian.com': [_make_agent()]}
        # No metadata — fallback to email-derived name
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, {})
        result = discover_aegis_accounts(sdk)

        assert result[0]['display_name'] == 'Noname'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_concurrent_checks_all_accounts(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('a@praetorian.com'), _account('b@praetorian.com')]
        agents_map = {
            'a@praetorian.com': [_make_agent()],
            'b@praetorian.com': [],
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, {})
        discover_aegis_accounts(sdk)

        # Verify per-account agent checks were made with correct account headers
        checked_accounts = {
            call.kwargs.get('headers', {}).get('account')
            for call in mock_requests.get.call_args_list
            if '/agent/enhanced' in call.args[0]
        }
        assert checked_accounts == {'a@praetorian.com', 'b@praetorian.com'}

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_frozen_account_shows_paused(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('frozen@praetorian.com')]
        agents_map = {'frozen@praetorian.com': [_make_agent()]}
        metadata = {
            'types': {'frozen@praetorian.com': 'MANAGED'},
            'subscriptions': {'frozen@praetorian.com': _active_subscription()},
            'frozen': {'frozen@praetorian.com': True},
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, metadata)
        result = discover_aegis_accounts(sdk)

        assert result[0]['status'] == 'Paused'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_expired_pilot_shows_completed(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('pilot@praetorian.com')]
        agents_map = {'pilot@praetorian.com': [_make_agent()]}
        metadata = {
            'types': {'pilot@praetorian.com': 'PILOT'},
            'subscriptions': {'pilot@praetorian.com': _expired_subscription()},
        }
        sdk = _make_sdk(accounts, agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, metadata)
        result = discover_aegis_accounts(sdk)

        assert result[0]['status'] == 'Completed'


class TestCalculateStatus:
    def test_active_subscription(self):
        from praetorian_cli.sdk.entities.account_discovery import _calculate_status
        metadata = {
            'types': {'a@b.com': 'MANAGED'},
            'subscriptions': {'a@b.com': _active_subscription()},
            'frozen': {},
        }
        assert _calculate_status('a@b.com', metadata) == 'Active'

    def test_no_subscription_is_setup(self):
        from praetorian_cli.sdk.entities.account_discovery import _calculate_status
        metadata = {'types': {}, 'subscriptions': {}, 'frozen': {}}
        assert _calculate_status('a@b.com', metadata) == 'Setup'

    def test_frozen_overrides_active(self):
        from praetorian_cli.sdk.entities.account_discovery import _calculate_status
        metadata = {
            'types': {'a@b.com': 'MANAGED'},
            'subscriptions': {'a@b.com': _active_subscription()},
            'frozen': {'a@b.com': True},
        }
        assert _calculate_status('a@b.com', metadata) == 'Paused'

    def test_completed_not_overridden_by_frozen(self):
        from praetorian_cli.sdk.entities.account_discovery import _calculate_status
        metadata = {
            'types': {'a@b.com': 'PILOT'},
            'subscriptions': {'a@b.com': _expired_subscription()},
            'frozen': {'a@b.com': True},
        }
        assert _calculate_status('a@b.com', metadata) == 'Completed'


class TestLoadAgentsForAccounts:
    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_loads_agents_from_multiple_accounts(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        agents_map = {
            'acme@praetorian.com': [_make_agent('srv1'), _make_agent('srv2')],
            'beta@praetorian.com': [_make_agent('srv3')],
        }
        sdk = _make_sdk([], agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, {})

        selected = [
            {'account_email': 'acme@praetorian.com', 'display_name': 'Acme', 'status': 'Active'},
            {'account_email': 'beta@praetorian.com', 'display_name': 'Beta', 'status': 'Completed'},
        ]
        result, failed = load_agents_for_accounts(sdk, selected)

        assert len(result) == 3
        assert failed == []
        # Results are now sorted deterministically by account name, hostname
        assert result[0][1]['display_name'] == 'Acme'
        assert result[2][1]['display_name'] == 'Beta'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_loads_v2_endpoints_from_multiple_accounts(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        agents_map = {'acme@praetorian.com': []}
        endpoints_map = {
            'acme@praetorian.com': [
                {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
            ],
        }
        sdk = _make_sdk([], agents_map)
        mock_requests.get.side_effect = _mock_requests_get(agents_map, {}, endpoints_map)

        selected = [
            {'account_email': 'acme@praetorian.com', 'display_name': 'Acme', 'status': 'Active'},
        ]
        result, failed = load_agents_for_accounts(sdk, selected)

        assert failed == []
        assert len(result) == 1
        agent, account = result[0]
        assert account['display_name'] == 'Acme'
        assert agent.version == 'v2'
        assert agent.endpoint_id == 'endpoint-1'

    def test_retries_load_when_endpoint_probe_fails_after_empty_agent_probe(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        sdk = _make_sdk([], {'endpoint@praetorian.com': []})
        calls = {'endpoint': 0}

        def mock_get(url, headers=None, params=None, timeout=None):
            params = params or {}
            resp = MagicMock()
            if '/agent/enhanced' in url:
                resp.status_code = 200
                resp.json.return_value = []
            elif '/my' in url and params.get('key') == '#endpoint#':
                calls['endpoint'] += 1
                resp.status_code = 503 if calls['endpoint'] == 1 else 200
                resp.json.return_value = {'endpoints': [
                    {'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'sensor-1'},
                ]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.time.sleep', lambda _seconds: None)

        selected = [
            {'account_email': 'endpoint@praetorian.com', 'display_name': 'Endpoint', 'status': 'Active'},
        ]
        result, failed = load_agents_for_accounts(sdk, selected)

        assert failed == []
        assert calls['endpoint'] == 2
        assert len(result) == 1
        assert result[0][0].endpoint_id == 'endpoint-1'

    @patch('praetorian_cli.sdk.entities.account_discovery.requests')
    def test_loads_schedules_from_multiple_accounts(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import load_schedules_for_accounts

        schedules_by_account = {
            'acme@praetorian.com': [{'scheduleId': 's1', 'capabilityName': 'scan'}],
            'beta@praetorian.com': [{'scheduleId': 's2', 'capabilityName': 'enum'}],
        }

        def mock_get(url, headers=None, params=None, timeout=None):
            account_email = (headers or {}).get('account', '')
            resp = MagicMock()
            if '/my' in url and params and params.get('key') == '#capability_schedule#':
                schedules = schedules_by_account.get(account_email, [])
                resp.status_code = 200
                resp.json.return_value = {'capabilityschedules': schedules}
            else:
                resp.status_code = 404
                resp.json.return_value = {}
            return resp

        sdk = _make_sdk([])
        mock_requests.get.side_effect = mock_get

        selected = [
            {'account_email': 'acme@praetorian.com', 'display_name': 'Acme', 'status': 'Active'},
            {'account_email': 'beta@praetorian.com', 'display_name': 'Beta', 'status': 'Completed'},
        ]
        result, failed = load_schedules_for_accounts(sdk, selected)

        assert len(result) == 2
        assert failed == []
        sched_ids = {r[0]['scheduleId'] for r in result}
        assert sched_ids == {'s1', 's2'}


class TestTruncateEmail:
    def test_short_email_unchanged(self):
        from praetorian_cli.sdk.entities.account_discovery import truncate_email
        assert truncate_email('short@p.com', 16) == 'short@p.com'

    def test_long_email_truncated(self):
        from praetorian_cli.sdk.entities.account_discovery import truncate_email
        result = truncate_email('chariot+cushwake@praetorian.com', 16)
        assert len(result) == 16
        assert result.endswith('...')


class TestFriendlyNameFromEmail:
    def test_chariot_plus_pattern(self):
        from praetorian_cli.sdk.entities.account_discovery import _friendly_name_from_email
        assert _friendly_name_from_email('chariot+cushwake@praetorian.com') == 'Cushwake'

    def test_chariot_plus_underscores(self):
        from praetorian_cli.sdk.entities.account_discovery import _friendly_name_from_email
        result = _friendly_name_from_email('chariot+american_family_insurance@praetorian.com')
        assert result == 'American Family Insurance'

    def test_plain_email(self):
        from praetorian_cli.sdk.entities.account_discovery import _friendly_name_from_email
        assert _friendly_name_from_email('noname@praetorian.com') == 'Noname'


class TestFetchAccountEndpoints:
    def test_keeps_offline_identity_and_enriches_live_endpoint(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import _fetch_account_endpoints

        def mock_get(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            resp.status_code = 200
            if url.endswith('/endpoint/list'):
                resp.json.return_value = {'endpoints': [
                    {
                        'endpointId': 'endpoint-offline',
                        'kind': 'aegis',
                        'lifecycleState': 'Active',
                        'profile': {'hostname': 'offline', 'os': 'linux'},
                    },
                    {
                        'endpointId': 'endpoint-live',
                        'kind': 'aegis',
                        'lifecycleState': 'Active',
                        'profile': {'hostname': 'live', 'os': 'unknown'},
                    },
                ]}
            elif url.endswith('/endpoint'):
                resp.json.return_value = []
            elif (params or {}).get('key') == '#endpoint#':
                resp.json.return_value = {'endpoints': [{
                    'endpointId': 'endpoint-live',
                    'kind': 'aegis',
                    'hostname': 'live',
                    'os': 'linux',
                }]}
            elif (params or {}).get('key') == '#endpointaegistunnelstate#':
                resp.json.return_value = {'tunnelStates': [{
                    'endpointId': 'endpoint-live',
                    'cloudflaredStatus': {
                        'status': 'configured',
                        'hostname': 'live.example.com',
                    },
                }]}
            else:
                resp.json.return_value = {'endpointStatuses': [{
                    'endpointId': 'endpoint-live',
                    'cloudflared': {'state': 'running'},
                }]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)

        endpoints = _fetch_account_endpoints('https://api.example.com', {})

        assert [
            endpoint.get('endpointId') or endpoint.get('endpoint_id')
            for endpoint in endpoints
        ] == ['endpoint-offline', 'endpoint-live']
        assert endpoints[0]['profile']['os'] == 'linux'
        assert endpoints[1]['os'] == 'linux'
        assert endpoints[1]['cloudflaredStatus'] == {
            'status': 'configured',
            'hostname': 'live.example.com',
        }

    def test_inventory_follows_cursors_and_excludes_revoked_endpoints(
        self,
        monkeypatch,
    ):
        from praetorian_cli.sdk.entities.account_discovery import (
            _fetch_account_endpoint_inventory,
        )

        calls = []

        def mock_get(url, headers=None, params=None, timeout=None):
            calls.append(dict(params or {}))
            resp = MagicMock()
            resp.status_code = 200
            if not params:
                resp.json.return_value = {
                    'endpoints': [{
                        'endpointId': 'endpoint-1',
                        'kind': 'aegis',
                        'lifecycleState': 'Active',
                    }],
                    'cursor': 'next-page',
                }
            else:
                resp.json.return_value = {'endpoints': [
                    {
                        'endpointId': 'endpoint-revoked',
                        'kind': 'aegis',
                        'lifecycleState': 'Revoked',
                    },
                    {
                        'endpointId': 'endpoint-2',
                        'kind': 'aegis',
                        'lifecycleState': 'Active',
                    },
                ]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr(
            'praetorian_cli.sdk.entities.account_discovery.requests',
            requests_mock,
        )

        endpoints = _fetch_account_endpoint_inventory(
            'https://api.example.com',
            {},
        )

        assert [endpoint['endpointId'] for endpoint in endpoints] == [
            'endpoint-1',
            'endpoint-2',
        ]
        assert calls == [{}, {'cursor': 'next-page'}]


class TestFetchLiveAccountEndpoints:
    def test_follows_paginated_offsets(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import _fetch_account_live_endpoints

        calls = []

        def mock_get(url, headers=None, params=None, timeout=None):
            calls.append(dict(params or {}))
            resp = MagicMock()
            resp.status_code = 200
            if 'offset' not in (params or {}):
                resp.json.return_value = {
                    'endpoints': [{'endpointId': 'endpoint-1', 'kind': 'aegis'}],
                    'offset': {'next': 'page-2'},
                }
            else:
                assert json.loads(params['offset']) == {'next': 'page-2'}
                resp.json.return_value = {'endpoints': [{'endpointId': 'endpoint-2', 'kind': 'aegis'}]}
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)

        endpoints = _fetch_account_live_endpoints('https://api.example.com', {'Authorization': 'Bearer token'})

        assert [endpoint['endpointId'] for endpoint in endpoints] == ['endpoint-1', 'endpoint-2']
        assert calls == [
            {'key': '#endpoint#'},
            {'key': '#endpoint#', 'offset': json.dumps({'next': 'page-2'})},
        ]

    def test_stops_on_reordered_repeated_offset(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import _fetch_account_live_endpoints

        offsets = [
            {'cursor': 'same', 'page': 2},
            {'page': 2, 'cursor': 'same'},
        ]
        calls = 0

        def mock_get(url, headers=None, params=None, timeout=None):
            nonlocal calls
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {'endpoints': [], 'offset': offsets[calls]}
            calls += 1
            return resp

        requests_mock = MagicMock()
        requests_mock.get.side_effect = mock_get
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)

        assert _fetch_account_live_endpoints('https://api.example.com', {}) is None
        assert calls == 2

    def test_handles_null_body_as_empty_page(self, monkeypatch):
        from praetorian_cli.sdk.entities.account_discovery import _fetch_account_live_endpoints

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = None
        requests_mock = MagicMock()
        requests_mock.get.return_value = resp
        monkeypatch.setattr('praetorian_cli.sdk.entities.account_discovery.requests', requests_mock)

        assert _fetch_account_live_endpoints('https://api.example.com', {}) == []


class TestFlattenResponse:
    def test_flattens_dict_of_lists(self):
        from praetorian_cli.sdk.entities.account_discovery import _flatten_response
        data = {'settings': [{'name': 'a'}, {'name': 'b'}], 'offset': []}
        result = _flatten_response(data)
        assert len(result) == 2
        assert result[0]['name'] == 'a'

    def test_passes_through_list(self):
        from praetorian_cli.sdk.entities.account_discovery import _flatten_response
        data = [{'name': 'a'}]
        assert _flatten_response(data) == data

    @pytest.mark.parametrize('data', [None, '', 0])
    def test_non_collection_body_is_empty(self, data):
        from praetorian_cli.sdk.entities.account_discovery import _flatten_response
        assert _flatten_response(data) == []


class TestExtractEmail:
    def test_from_username(self):
        from praetorian_cli.sdk.entities.account_discovery import _extract_email
        assert _extract_email({'username': 'foo@bar.com'}) == 'foo@bar.com'

    def test_from_key(self):
        from praetorian_cli.sdk.entities.account_discovery import _extract_email
        assert _extract_email({'key': '#configuration#customer_type#foo@bar.com'}) == 'foo@bar.com'

    def test_none_when_missing(self):
        from praetorian_cli.sdk.entities.account_discovery import _extract_email
        assert _extract_email({'key': '#configuration#customer_type'}) is None


class TestIncompleteAccountInventory:
    @pytest.fixture
    def inventory(self, monkeypatch):
        from praetorian_cli.sdk.entities import account_discovery
        from requests.exceptions import ConnectionError

        state = {
            'legacy': [{'client_id': 'C.legacy', 'hostname': 'legacy-host'}],
            'v2': [{'endpointId': 'endpoint-1', 'kind': 'aegis', 'hostname': 'v2-host'}],
            'failures': set(),
            'transport': False,
            'headers': [],
        }

        def get(url, headers=None, params=None, timeout=None):
            params = params or {}
            state['headers'].append(headers)
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {}
            if params.get('allTenants') == 'true':
                return response
            if url.endswith('/agent/enhanced'):
                source = 'legacy'
                response.json.return_value = state['legacy']
            elif url.endswith('/endpoint/list'):
                source = 'v2 durable'
                response.json.return_value = {'endpoints': state['v2']}
            elif url.endswith('/endpoint'):
                source = 'v2 identities'
                response.json.return_value = [
                    {'endpoint_id': row['endpointId'], 'hostname': row['hostname']}
                    for row in state['v2']
                ]
            elif params.get('key') == '#endpoint#':
                source = 'v2 live'
                response.json.return_value = {'endpoints': state['v2']}
            else:
                source = params.get('key')
            if source in state['failures'] or source.split()[0] in state['failures']:
                if state['transport']:
                    raise ConnectionError('upstream connection refused')
                response.status_code = 503
                response.text = 'backend unavailable'
            return response

        monkeypatch.setattr(account_discovery.requests, 'get', get)
        monkeypatch.setattr(account_discovery.time, 'sleep', lambda _seconds: None)
        return state

    @pytest.mark.parametrize('failed_source', ['legacy', 'v2'])
    @pytest.mark.parametrize('transport', [False, True])
    def test_load_keeps_opposite_inventory_and_warns(
        self, inventory, failed_source, transport,
    ):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['failures'] = {failed_source}
        inventory['transport'] = transport
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}
        warnings = []

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append)

        expected = 'v2-host' if failed_source == 'legacy' else 'legacy-host'
        assert [(agent.hostname, acct) for agent, acct in rows] == [(expected, account)]
        assert failed == []
        error = 'upstream connection refused' if transport else '503 from'
        assert any(
            'tenant@example.com' in warning and failed_source in warning and error in warning
            and (transport or 'backend unavailable' in warning)
            for warning in warnings
        )

    @pytest.mark.parametrize('failed_source', ['legacy', 'v2'])
    @pytest.mark.parametrize('transport', [False, True])
    def test_discovery_keeps_opposite_inventory_and_logs_warning(
        self, inventory, caplog, failed_source, transport,
    ):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        inventory['failures'] = {failed_source}
        inventory['transport'] = transport
        sdk = _make_sdk([_account('tenant@example.com')])

        accounts = discover_aegis_accounts(sdk)

        assert [(acct['account_email'], acct['agent_count']) for acct in accounts] == [
            ('tenant@example.com', 1),
        ]
        error = 'upstream connection refused' if transport else '503'
        assert any(
            'tenant@example.com' in record.message
            and failed_source in record.message and error in record.message
            for record in caplog.records
        )

    @pytest.mark.parametrize('transport', [False, True])
    def test_total_failure_is_reported_as_failed_not_empty(self, inventory, transport):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['failures'] = {'legacy', 'v2'}
        inventory['transport'] = transport
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}
        warnings = []

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append)

        assert rows == []
        assert failed == ['Tenant']
        for source in ('legacy', 'v2'):
            assert any('tenant@example.com' in warning and source in warning for warning in warnings)

    @pytest.mark.parametrize('failed_source', ['legacy', 'v2'])
    def test_partial_empty_is_reported_as_incomplete(self, inventory, failed_source):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['legacy'] = []
        inventory['v2'] = []
        inventory['failures'] = {failed_source}
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}
        warnings = []

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append)

        assert rows == []
        assert failed == ['Tenant']
        assert any(
            'tenant@example.com' in warning and failed_source in warning
            for warning in warnings
        )

    def test_genuine_empty_has_no_warning_or_failed_account(self, inventory):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['legacy'] = []
        inventory['v2'] = []
        warnings = []
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}

        assert load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append) == ([], [])
        assert warnings == []

    def test_successful_retry_does_not_leave_inventory_marked_incomplete(self, inventory, monkeypatch):
        from praetorian_cli.sdk.entities import account_discovery

        inventory['legacy'] = []
        inventory['v2'] = []
        inventory['failures'] = {'legacy'}
        get = account_discovery.requests.get

        def recover_after_first_request(url, **kwargs):
            response = get(url, **kwargs)
            if url.endswith('/agent/enhanced'):
                inventory['failures'].clear()
            return response

        monkeypatch.setattr(account_discovery.requests, 'get', recover_after_first_request)
        warnings = []
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}

        rows, failed = account_discovery.load_agents_for_accounts(
            _make_sdk([]), [account], on_warning=warnings.append,
        )

        assert rows == []
        assert failed == []
        assert warnings == []

    def test_default_warning_uses_logger(self, inventory, caplog):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['failures'] = {'legacy'}
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account])

        assert [agent.endpoint_id for agent, _acct in rows] == ['endpoint-1']
        assert failed == []
        assert any(
            'tenant@example.com' in record.message and 'legacy' in record.message
            for record in caplog.records
        )

    @pytest.mark.parametrize('source', [
        'v2 live', '#endpointaegistunnelstate#', '#endpointaegisstatus#',
    ])
    @pytest.mark.parametrize('transport', [False, True])
    def test_optional_enrichment_failure_preserves_durable_endpoint(
        self, inventory, source, transport,
    ):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['legacy'] = []
        inventory['failures'] = {source}
        inventory['transport'] = transport
        warnings = []
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append)

        assert [(agent.endpoint_id, agent.hostname) for agent, _acct in rows] == [
            ('endpoint-1', 'v2-host'),
        ]
        assert failed == []
        error = 'upstream connection refused' if transport else '503'
        assert any('tenant@example.com' in warning and error in warning for warning in warnings)

    @pytest.mark.parametrize('transport', [False, True])
    def test_durable_inventory_failure_falls_back_to_endpoint_identities(
        self, inventory, transport,
    ):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        inventory['legacy'] = []
        inventory['failures'] = {'v2 durable', 'v2 live'}
        inventory['transport'] = transport
        warnings = []
        account = {'account_email': 'tenant@example.com', 'display_name': 'Tenant'}

        rows, failed = load_agents_for_accounts(_make_sdk([]), [account], on_warning=warnings.append)

        assert [agent.endpoint_id for agent, _acct in rows] == ['endpoint-1']
        assert failed == []
        error = 'upstream connection refused' if transport else '503'
        assert any('tenant@example.com' in warning and error in warning for warning in warnings)

    def test_tenant_headers_are_isolated(self, inventory):
        from praetorian_cli.sdk.entities.account_discovery import load_agents_for_accounts

        sdk = _make_sdk([])
        shared_headers = {'Authorization': 'Bearer test-token', 'account': 'original@example.com'}
        sdk.keychain.headers.return_value = shared_headers
        accounts = [
            {'account_email': 'first@example.com', 'display_name': 'First'},
            {'account_email': 'second@example.com', 'display_name': 'Second'},
        ]

        rows, failed = load_agents_for_accounts(sdk, accounts)

        assert {(agent.hostname, acct['account_email']) for agent, acct in rows} == {
            ('legacy-host', 'first@example.com'),
            ('v2-host', 'first@example.com'),
            ('legacy-host', 'second@example.com'),
            ('v2-host', 'second@example.com'),
        }
        assert failed == []
        assert shared_headers == {
            'Authorization': 'Bearer test-token', 'account': 'original@example.com',
        }
        assert {headers['account'] for headers in inventory['headers']} == {
            'first@example.com', 'second@example.com',
        }
        assert all(headers is not shared_headers for headers in inventory['headers'])
