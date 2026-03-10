"""Tests for account discovery with aegis agent filtering."""
import pytest
from unittest.mock import MagicMock, patch


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


def _mock_requests_get(agents_by_account, metadata=None):
    """Create a mock for requests.get that simulates API endpoints.

    metadata keys: types, subscriptions, frozen, display_names
    Each maps email -> value for allTenants bulk responses.
    """
    metadata = metadata or {}
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
    def test_account_metadata_extraction(self, mock_requests):
        from praetorian_cli.sdk.entities.account_discovery import discover_aegis_accounts

        accounts = [_account('client@praetorian.com')]
        agents_map = {'client@praetorian.com': [_make_agent()]}
        metadata = {
            'types': {'client@praetorian.com': 'MANAGED'},
            'display_names': {'client@praetorian.com': 'Cushman & Wakefield'},
            'subscriptions': {'client@praetorian.com': {'startDate': '2024-01-01', 'endDate': '2027-12-31'}},
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
            'subscriptions': {'frozen@praetorian.com': {'startDate': '2024-01-01', 'endDate': '2027-12-31'}},
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
            'subscriptions': {'pilot@praetorian.com': {'startDate': '2023-01-01', 'endDate': '2023-06-30'}},
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
            'subscriptions': {'a@b.com': {'startDate': '2024-01-01', 'endDate': '2027-12-31'}},
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
            'subscriptions': {'a@b.com': {'startDate': '2024-01-01', 'endDate': '2027-12-31'}},
            'frozen': {'a@b.com': True},
        }
        assert _calculate_status('a@b.com', metadata) == 'Paused'

    def test_completed_not_overridden_by_frozen(self):
        from praetorian_cli.sdk.entities.account_discovery import _calculate_status
        metadata = {
            'types': {'a@b.com': 'PILOT'},
            'subscriptions': {'a@b.com': {'startDate': '2023-01-01', 'endDate': '2023-06-30'}},
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
        result = load_schedules_for_accounts(sdk, selected)

        assert len(result) == 2
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
