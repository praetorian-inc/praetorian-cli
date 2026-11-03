"""Exact queued-run identity and consumer-visible operation outcomes."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from conftest import ENQUEUED, JOB_ID, PREFIX, SECRET, lifecycle_calls, operation


@pytest.mark.parametrize('status,expected_exit', [
    ('enqueued', 0), ('succeeded', 0), ('failed', 1), ('superseded', 1),
    ('unavailable', 1), ('unknown', 1), (None, 1),
])
def test_result_uses_exact_run_discriminator_and_preserves_failure_status(api, invoke, status, expected_exit):
    api.result = operation(status=status)
    if status is None:
        api.result.pop('status')
    result = invoke(['result', '--job-id', JOB_ID, '--enqueued', ENQUEUED])
    assert result.exit_code == expected_exit, result.output
    calls = lifecycle_calls(api)
    assert len(calls) == 1
    assert calls[0]['method'] == 'GET'
    target = calls[0]['target']
    assert urlsplit(target).path == PREFIX + 'results'
    assert parse_qs(urlsplit(target).query) == {'job_id': [JOB_ID], 'enqueued': [ENQUEUED]}
    assert '%23job%23' in target
    assert 'enqueued=2026-11-02T17%3A19%3A25.123456789%2B00%3A00' in target
    assert JOB_ID in result.output and ENQUEUED in result.output
    if status is not None:
        assert '"status": ' + json.dumps(status) in result.output
    assert SECRET not in result.output


@pytest.mark.parametrize('status,exit_code', [('failed', 1), ('superseded', 1), ('unavailable', 1), ('succeeded', 0)])
def test_execute_outcome_is_not_unconditional_success(api, invoke, status, exit_code):
    api.result = operation(status=status)
    result = invoke(['delete', '--yes'])
    assert result.exit_code == exit_code, result.output
    assert '"status": ' + json.dumps(status) in result.output
    assert JOB_ID in result.output and ENQUEUED in result.output
    assert [c['target'] for c in lifecycle_calls(api)] == [PREFIX + 'preview', PREFIX + 'execute']


@pytest.mark.parametrize('missing', ['job_id', 'enqueued'])
def test_enqueued_without_exact_run_identifiers_is_failure(api, invoke, missing):
    api.result.pop(missing)
    result = invoke(['delete', '--yes'])
    assert result.exit_code == 1
    assert 'Queued operation did not return' in result.output
