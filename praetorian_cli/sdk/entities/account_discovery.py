"""Account discovery with aegis agent filtering.

Fetches account metadata in bulk via allTenants API calls, then concurrently
checks each account for aegis agents to build enriched account info.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def discover_aegis_accounts(sdk, on_progress=None) -> List[dict]:
    """Discover accounts that have aegis agents registered.

    Fetches metadata (type, status, display name) in bulk, then concurrently
    checks each authorized account for agents.

    Args:
        sdk: Chariot SDK instance
        on_progress: Optional callback(checked: int, total: int, email: str)

    Returns a list of dicts with keys:
        account_email, display_name, status, account_type, agent_count
    """
    accounts, _ = sdk.accounts.list()
    current = sdk.accounts.current_principal()

    # Get unique authorized account emails (accounts we can assume into)
    authorized = set()
    for acct in accounts:
        name = acct.get('name', '')
        if name and name != current:
            authorized.add(name)

    sorted_accounts = sorted(authorized)
    total = len(sorted_accounts)

    # Pre-compute shared values
    base_url = sdk.keychain.base_url()
    auth_headers = dict(sdk.keychain.headers())

    # Fetch all metadata in bulk (3 calls instead of N*2 per-account calls)
    metadata = _fetch_all_metadata(base_url, auth_headers)

    results = []
    checked = [0]
    lock = threading.Lock()

    def _check_account(account_email):
        """Check a single account for agents. Thread-safe."""
        try:
            headers = dict(auth_headers)
            headers['account'] = account_email

            resp = requests.get(
                f'{base_url}/agent/enhanced',
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                logger.debug('Agent check for %s returned status %d', account_email, resp.status_code)
                return None

            agents_data = resp.json()
            if not agents_data:
                return None

            return _build_account_info(
                account_email,
                len(agents_data),
                metadata,
            )
        except Exception as e:
            logger.debug('Agent check failed for %s: %s', account_email, e)
            return None
        finally:
            with lock:
                checked[0] += 1
                if on_progress:
                    on_progress(checked[0], total, account_email)

    # Run agent checks concurrently (4 threads)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_check_account, email): email for email in sorted_accounts}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda r: r['account_email'])
    return results


def _fetch_all_metadata(base_url: str, auth_headers: dict) -> dict:
    """Fetch customer type, subscription, frozen, and display name for all tenants.

    Makes 2 bulk API calls with allTenants=true:
      1. #configuration# — customer_type and subscription (dates for status calc)
      2. #setting# — frozen flag and display-name
    """
    result = {
        'types': {},
        'subscriptions': {},
        'frozen': {},
        'display_names': {},
    }

    def _get(params):
        try:
            resp = requests.get(
                f'{base_url}/my',
                headers=auth_headers,
                params=params,
                timeout=30,
            )
            if resp.status_code == 200:
                return _flatten_response(resp.json())
            logger.debug('Metadata fetch for %s returned status %d', params.get('key'), resp.status_code)
        except Exception as e:
            logger.debug('Metadata fetch failed for %s: %s', params.get('key'), e)
        return []

    # Fetch all configurations: customer_type + subscription
    for item in _get({'key': '#configuration#', 'allTenants': 'true'}):
        email = _extract_email(item)
        if not email:
            continue
        name = item.get('name', '')
        if name == 'customer_type' and item.get('value'):
            result['types'][email] = item['value']
        elif name == 'subscription' and item.get('value'):
            val = item['value']
            if isinstance(val, dict):
                result['subscriptions'][email] = val

    # Fetch all settings: frozen + display-name
    for item in _get({'key': '#setting#', 'allTenants': 'true'}):
        email = _extract_email(item)
        if not email:
            continue
        name = item.get('name', '')
        if name == 'frozen':
            result['frozen'][email] = (item.get('value') == 'true')
        elif name == 'display-name' and item.get('value'):
            result['display_names'][email] = item['value']

    return result


def _extract_email(item: dict) -> Optional[str]:
    """Extract the tenant email from an allTenants API response item."""
    email = item.get('username')
    if email:
        return email
    # Fallback: parse from key like #configuration#customer_type#email@example.com
    key = item.get('key', '')
    parts = key.split('#')
    for part in parts:
        if '@' in part:
            return part
    return None


def _flatten_response(data) -> List[dict]:
    """Flatten a /my API response dict into a list of record dicts.

    The /my endpoint returns {"someKey": [records...], "offset": ...}.
    """
    if isinstance(data, list):
        return data
    records = []
    for value in data.values():
        if isinstance(value, list):
            records.extend(value)
        elif isinstance(value, dict):
            records.extend(_flatten_response(value))
    return records


def _calculate_status(email: str, metadata: dict) -> str:
    """Calculate account status from subscription dates and frozen flag.

    Mirrors the frontend useCustomerStatus logic.
    """
    is_frozen = metadata['frozen'].get(email, False)
    subscription = metadata['subscriptions'].get(email, {})
    customer_type = metadata['types'].get(email, '')
    start_str = subscription.get('startDate')
    end_str = subscription.get('endDate')

    if not start_str or not end_str:
        date_status = 'Setup'
    else:
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start = datetime.fromisoformat(start_str.replace('Z', '+00:00')).replace(tzinfo=None)
            end = datetime.fromisoformat(end_str.replace('Z', '+00:00')).replace(tzinfo=None)

            if today > end and customer_type in ('PILOT', 'ENGAGEMENT'):
                date_status = 'Completed'
            elif today < start:
                days_until = (start - today).days
                date_status = 'Upcoming' if days_until <= 30 else 'Setup'
            else:
                date_status = 'Active'
        except (ValueError, TypeError):
            date_status = 'Active'

    if date_status == 'Completed':
        return 'Completed'
    if is_frozen:
        return 'Paused'
    return date_status


def _build_account_info(email: str, agent_count: int, metadata: dict) -> dict:
    """Build enriched account info from email and bulk metadata."""
    display_name = metadata['display_names'].get(email, '')
    if not display_name:
        display_name = _friendly_name_from_email(email)

    status = _calculate_status(email, metadata)
    account_type = metadata['types'].get(email, 'UNKNOWN')

    return {
        'account_email': email,
        'display_name': display_name,
        'status': status,
        'account_type': account_type,
        'agent_count': agent_count,
    }


def _friendly_name_from_email(email: str) -> str:
    """Derive a friendly display name from an email address.

    Handles chariot+name@praetorian.com pattern by extracting 'name'
    and converting underscores/hyphens to spaces with title case.
    """
    local = email.split('@')[0] if '@' in email else email
    # Strip chariot+ prefix
    if local.startswith('chariot+'):
        local = local[len('chariot+'):]
    # Strip common suffixes like -v7n, dvl0.qtn005--clibuu etc.
    # Clean up separators
    name = local.replace('_', ' ').replace('-', ' ')
    return name.title() if name else email


def _expand_status_code(code: str) -> str:
    """Expand single-letter status codes to full names."""
    mapping = {
        'A': 'ACTIVE',
        'C': 'COMPLETED',
        'P': 'PAUSED',
        'F': 'FROZEN',
    }
    return mapping.get(code, code.upper() if code else 'UNKNOWN')


def load_agents_for_accounts(sdk, selected_accounts: List[dict], on_progress=None) -> List[tuple]:
    """Load agents from multiple accounts concurrently with retry.

    Args:
        sdk: Chariot SDK instance
        selected_accounts: List of account info dicts from discover_aegis_accounts
        on_progress: Optional callback(checked: int, total: int, display_name: str)

    Returns:
        Tuple of (agent_tuples, failed_account_names) where agent_tuples is
        a list of (Agent, account_info) tuples and failed_account_names is
        a list of display names for accounts that failed after retry.
    """
    from praetorian_cli.sdk.entities.aegis import Agent

    base_url = sdk.keychain.base_url()
    auth_headers = dict(sdk.keychain.headers())
    total = len(selected_accounts)
    checked = [0]
    failed_accounts = []
    lock = threading.Lock()

    def _load_one(acct, attempt=1):
        email = acct['account_email']
        try:
            headers = dict(auth_headers)
            headers['account'] = email
            resp = requests.get(
                f'{base_url}/agent/enhanced',
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                return [(Agent.from_dict(d), acct) for d in resp.json()]
            logger.debug('Agent load for %s returned status %d (attempt %d)', email, resp.status_code, attempt)
            return None  # Signal failure (distinct from empty account)
        except Exception as e:
            logger.debug('Agent load failed for %s: %s (attempt %d)', email, e, attempt)
            return None
        finally:
            with lock:
                checked[0] += 1
                if on_progress:
                    on_progress(checked[0], total, acct.get('display_name', email))

    results = []
    retry_accounts = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_load_one, acct): acct for acct in selected_accounts}
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                retry_accounts.append(futures[future])
            else:
                results.extend(result)

    # Retry failed accounts once
    if retry_accounts:
        logger.debug('Retrying %d failed account(s)', len(retry_accounts))
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_load_one, acct, 2): acct for acct in retry_accounts}
            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    acct = futures[future]
                    with lock:
                        failed_accounts.append(acct.get('display_name', acct['account_email']))
                else:
                    results.extend(result)

    if failed_accounts:
        logger.warning('Failed to load agents for: %s', ', '.join(failed_accounts))

    # Sort deterministically by account name then hostname to avoid
    # non-deterministic ordering from concurrent thread completion.
    results.sort(key=lambda t: (
        t[1].get('display_name', '').lower(),
        t[0].hostname.lower() if t[0].hostname else '',
    ))

    return results, failed_accounts


def load_schedules_for_accounts(sdk, selected_accounts: List[dict]) -> List[tuple]:
    """Load schedules from multiple accounts concurrently.

    Args:
        sdk: Chariot SDK instance
        selected_accounts: List of account info dicts from discover_aegis_accounts

    Returns:
        List of (schedule_dict, account_info) tuples.
    """
    base_url = sdk.keychain.base_url()
    auth_headers = dict(sdk.keychain.headers())

    def _load_one(acct):
        email = acct['account_email']
        try:
            headers = dict(auth_headers)
            headers['account'] = email
            resp = requests.get(
                f'{base_url}/my',
                headers=headers,
                params={'key': '#capability_schedule#'},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.debug('Schedule load for %s returned status %d', email, resp.status_code)
                return []
            data = resp.json()
            schedules = data.get('capabilityschedules', [])
            return [(sched, acct) for sched in schedules]
        except Exception as e:
            logger.debug('Schedule load failed for %s: %s', email, e)
            return []

    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_load_one, acct): acct for acct in selected_accounts}
        for future in as_completed(futures):
            results.extend(future.result())

    return results


def truncate_email(email: str, max_len: int = 16) -> str:
    """Truncate email to max_len characters with '...' suffix if needed."""
    if len(email) <= max_len:
        return email
    return email[:max_len - 3] + '...'
