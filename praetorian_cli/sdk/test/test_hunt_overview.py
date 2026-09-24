from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from praetorian_cli.ui.hunt_overview import (
    MAX_AGENT_SUMMARY_LENGTH,
    MAX_SCOPE_SUMMARY_LENGTH,
    UNAVAILABLE,
    build_hunt_overview,
    format_projected_cost,
    format_remaining_time,
    highest_hunt_severity,
    summarize_hunt_scope,
    summarize_root_agents,
)


def _usage(cost, total_tokens=150, currency='USD'):
    return {
        'total': {
            'model': '',
            'cost': cost,
            'call_count': 3,
            'input_tokens': 100,
            'output_tokens': 50,
            'total_tokens': total_tokens,
        },
        'by_model': [],
        'currency': currency,
    }


@pytest.mark.parametrize(
    ('cost_status', 'expected'),
    [
        (_usage(1.5), '$1.50'),
        (_usage(0), '$0.00'),
        (_usage(-0.0), '$0.00'),
        (_usage(1234.567), '$1,234.57'),
        (_usage(0, total_tokens=0), UNAVAILABLE),
        (_usage(1.5, currency='EUR'), UNAVAILABLE),
        (None, UNAVAILABLE),
        ({'currency': 'USD'}, UNAVAILABLE),
    ],
)
def test_projected_cost_matches_webui_states(cost_status, expected):
    assert format_projected_cost(cost_status) == expected


def test_remaining_time_matches_webui_and_terminal_states():
    now = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    assert format_remaining_time({
        'status': 'active',
        'expiresAt': '2026-01-01T12:05:00Z',
    }, now=now) == '2h 5m'
    assert format_remaining_time({
        'status': 'active',
        'expiresAt': '2026-01-01T09:00:00Z',
    }, now=now) == 'Expired'
    for status in ('completed', 'expired', 'stopped', 'errored'):
        assert format_remaining_time({
            'status': status,
            'expiresAt': '2026-01-01T12:05:00Z',
        }, now=now) == UNAVAILABLE


def test_highest_severity_uses_hunt_linked_risk_statuses():
    findings = [
        {'status': 'OM', 'statusLabel': 'Open Medium'},
        {'risk': {'status': 'TC', 'statusLabel': 'Triaged Critical'}},
        {'status': 'OH', 'statusLabel': 'Open High'},
    ]

    assert highest_hunt_severity(findings) == 'critical'
    assert highest_hunt_severity([]) is None


def test_highest_severity_matches_webui_status_code_semantics():
    findings = [
        {'status': 'OH', 'statusLabel': 'Open High'},
        {
            'status': 'DCF',
            'statusLabel': 'Rejected False Positive',
            'severity': 'low',
        },
        {'status': '', 'statusLabel': 'Open Critical', 'severity': 'C'},
    ]

    assert highest_hunt_severity(findings) == 'critical'


def test_large_scope_and_agent_summaries_are_bounded():
    scope = [
        f'#asset#host-{index}.example.com#10.0.0.{index}'
        for index in range(100)
    ]
    conversations = [
        {'uuid': f'conversation-{index}', 'title': f'Agent iteration {index}'}
        for index in range(100)
    ]

    scope_summary = summarize_hunt_scope(scope)
    agent_summary = summarize_root_agents(conversations)

    assert 'host-0.example.com (10.0.0.0)' in scope_summary
    assert 'host-5.example.com' not in scope_summary
    assert '(+95 more)' in scope_summary
    assert len(scope_summary) <= MAX_SCOPE_SUMMARY_LENGTH
    assert 'Agent iteration 0' in agent_summary
    assert 'Agent iteration 5' not in agent_summary
    assert '(+95 more)' in agent_summary
    assert len(agent_summary) <= MAX_AGENT_SUMMARY_LENGTH


def test_agent_summary_matches_webui_newest_first_order():
    conversations = [
        {
            'uuid': 'old-root',
            'title': 'Older iteration',
            'created': '2026-01-01T00:00:00Z',
        },
        {
            'uuid': 'new-root',
            'title': 'Newest iteration',
            'created': '2026-01-03T00:00:00Z',
        },
        {
            'uuid': 'middle-root',
            'topic': 'Middle iteration',
            'created': '2026-01-02T00:00:00Z',
        },
    ]

    assert summarize_root_agents(conversations) == (
        'Newest iteration, Middle iteration, Older iteration'
    )


def test_webapplication_scope_label_matches_webui_key_rendering():
    assert summarize_hunt_scope([
        '#webapplication#https://app.example/#app.example',
    ]) == '#webapplication#https://app.example/ (app.example)'


def test_build_overview_collects_root_agents_findings_and_cost():
    class HuntAPI:
        def get_cost(self, hunt_id):
            assert hunt_id == 'hunt-1'
            return _usage(2.25)

        def list_root_conversations(self, hunt_id):
            assert hunt_id == 'hunt-1'
            return [
                {'uuid': 'root-1', 'title': 'Iteration one'},
                {'uuid': 'root-2', 'title': 'Iteration two'},
            ], None

        def list_findings(self, hunt_id, pages=1):
            assert hunt_id == 'hunt-1'
            assert pages == 100000
            return [{'status': 'OH', 'statusLabel': 'Open High'}], None

    overview = build_hunt_overview(
        SimpleNamespace(hunts=HuntAPI()),
        {
            'uuid': 'hunt-1',
            'status': 'active',
            'agent': 'hannibal',
            'iterationCount': 2,
            'expiresAt': '2026-01-01T12:05:00Z',
            'scope': ['#asset#db.example#10.0.0.5'],
        },
        now=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
    )

    assert overview == {
        'remaining': '2h 5m',
        'projected_cost': '$2.25',
        'root_agent': 'hannibal',
        'root_agent_count': 2,
        'iterations': 2,
        'highest_severity': 'High',
        'scope_summary': 'db.example (10.0.0.5)',
        'agent_summary': 'Iteration one, Iteration two',
    }


def test_overview_degrades_independent_api_errors_to_unavailable():
    class HuntAPI:
        def get_cost(self, _hunt_id):
            raise RuntimeError('unowned')

        def list_root_conversations(self, _hunt_id):
            raise RuntimeError('not supported')

        def list_findings(self, _hunt_id, pages=1):
            raise RuntimeError('temporarily unavailable')

    overview = build_hunt_overview(
        SimpleNamespace(hunts=HuntAPI()),
        {'uuid': 'hunt-1', 'status': 'completed'},
    )

    assert overview['projected_cost'] == UNAVAILABLE
    assert overview['root_agent_count'] == UNAVAILABLE
    assert overview['agent_summary'] == UNAVAILABLE
    assert overview['highest_severity'] == UNAVAILABLE
    assert overview['remaining'] == UNAVAILABLE
