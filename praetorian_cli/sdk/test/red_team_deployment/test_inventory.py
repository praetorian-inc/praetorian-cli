"""Selected-account inventory, safe recorded state, and read failures."""

import json

import pytest

from conftest import COMMIT, INFRA, PREFIX, SECRET, assert_no_execute, lifecycle_calls


@pytest.mark.parametrize('account,expected', [(None, 'profile-engagement'), ('selected-engagement', 'selected-engagement')])
def test_inventory_uses_selected_profile_and_account_headers(api, invoke, account, expected):
    result = invoke(['inventory'], account=account)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['status'] == 'missing'
    calls = lifecycle_calls(api)
    assert [(c['method'], c['target']) for c in calls] == [('GET', PREFIX + 'inventory')]
    assert calls[0]['headers']['account'] == expected
    assert calls[0]['headers']['Authorization'] == 'Bearer inert-loopback-token'
    assert api.calls[0]['target'] == '/selected/token'
    assert api.calls[0]['headers']['X-GUARD-API-KEY-ID'] == 'fixture-key'
    assert 'inert-loopback-token' not in result.output


@pytest.mark.parametrize('status,recorded', [('unknown', 'unknown'), ('stale', 'stale'), ('available', 'recorded')])
def test_inventory_preserves_safe_recorded_status_nodes_and_history(api, invoke, status, recorded):
    api.inventory = {
        'tenant_id': 'selected-engagement', 'status': status,
        'deployment': {
            'project_id': 'engagement-rt-ab', 'infra': INFRA,
            'collaborators': ['operator@example.test'],
            'recorded_status': recorded, 'recorded_at': 1793639965000,
            'age_seconds': 900, 'freshness_policy': 'Recorded apply history, not live health.',
            'nodes': [
                {'name': 'deployed-1', 'type': 'phishkit', 'recorded_status': 'recorded',
                 'planned_only': False, 'endpoints': [{'kind': 'public_ip', 'address': '203.0.113.7'}]},
                {'name': 'reserved-2', 'recorded_status': 'planned_only', 'planned_only': True},
            ],
        },
        'outputs': {'status': 'unavailable', 'reason': 'no non-sensitive allowlisted outputs'},
        'history': [{'timestamp': 1793639965000, 'success': False,
                     'principal': 'operator@example.test', 'infra': INFRA}],
    }
    result = invoke(['inventory'])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed['status'] == status
    assert parsed['deployment']['recorded_status'] == recorded
    assert parsed['deployment']['nodes'][0]['endpoints'][0]['address'] == '203.0.113.7'
    assert parsed['deployment']['nodes'][1]['planned_only'] is True
    assert parsed['deployment']['infra'] == INFRA
    assert parsed['deployment']['collaborators'] == ['operator@example.test']
    assert parsed['outputs']['status'] == 'unavailable'
    assert parsed['history'][0]['success'] is False
    assert parsed['history'][0]['principal'] == 'operator@example.test'
    assert 'not live health' in result.output
    assert all(word not in result.output for word in [SECRET, 'tfstate', 'tfvars', 'private_key', 'artifact_url'])
    assert [(c['method'], c['target']) for c in lifecycle_calls(api)] == [('GET', PREFIX + 'inventory')]


@pytest.mark.parametrize('command,route', [(['inventory'], 'inventory'), (['delete', '--yes'], 'preview')])
def test_denied_access_exposes_no_inventory_and_never_executes(api, invoke, command, route):
    api.errors[PREFIX + route] = (403, {'message': 'red-team access denied'})
    result = invoke(command)
    assert result.exit_code != 0
    assert '[403]' in result.output
    assert 'red-team access denied' in result.output
    for forbidden in ['engagement-rt-ab', 'Redacted deployment preview:', COMMIT, SECRET]:
        assert forbidden not in result.output
    assert [(c['method'], c['target']) for c in lifecycle_calls(api)] == [
        ('GET' if route == 'inventory' else 'POST', PREFIX + route),
    ]
    assert_no_execute(api)


def test_inventory_storage_failure_is_not_an_empty_success(api, invoke):
    api.errors[PREFIX + 'inventory'] = (503, {'message': 'could not read deployment history'})
    result = invoke(['inventory'])
    assert result.exit_code != 0
    assert '[503]' in result.output
    assert 'could not read deployment history' in result.output
    assert '"status": "missing"' not in result.output
    assert [c['target'] for c in lifecycle_calls(api)] == [PREFIX + 'inventory']
