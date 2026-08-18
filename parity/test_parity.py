"""Tests for the parity check system."""

import copy
import json
import os

import pytest

from parity.check_parity import check_parity, load_registry, REGISTRY_PATH


@pytest.fixture
def registry():
    return load_registry()


def test_registry_is_valid_json(registry):
    assert '_meta' in registry
    assert 'routes' in registry
    assert isinstance(registry['routes'], dict)


def test_route_count(registry):
    assert len(registry['routes']) == 206


def test_all_routes_have_required_fields(registry):
    for route, info in registry['routes'].items():
        assert 'disposition' in info, f'{route} missing disposition'
        assert 'gui' in info, f'{route} missing gui'
        assert 'cli_command' in info, f'{route} missing cli_command'
        assert 'sdk_entity' in info, f'{route} missing sdk_entity'


def test_excluded_routes_have_reason(registry):
    for route, info in registry['routes'].items():
        if info['disposition'] == 'excluded':
            assert info.get('reason'), f'{route} excluded without reason'


def test_planned_routes_have_ticket(registry):
    for route, info in registry['routes'].items():
        if info['disposition'] == 'planned':
            assert info.get('ticket'), f'{route} planned without ticket'


def test_covered_routes_have_cli_command(registry):
    for route, info in registry['routes'].items():
        if info['disposition'] == 'covered':
            assert info.get('cli_command'), f'{route} covered but no cli_command'


def test_check_passes_on_valid_registry(registry):
    gaps, summary = check_parity(registry)
    assert len(gaps) == 0, f'Unexpected gaps: {gaps}'
    assert summary['gap'] == 0


def test_check_fails_on_unknown_disposition():
    registry = {
        'routes': {
            '/test/route': {
                'cli_command': None,
                'sdk_entity': None,
                'gui': True,
                'disposition': 'bogus',
            }
        }
    }
    gaps, summary = check_parity(registry)
    assert len(gaps) == 1
    assert summary['gap'] == 1
    assert 'unknown disposition' in gaps[0]['reason']


def test_check_fails_on_planned_without_ticket():
    registry = {
        'routes': {
            '/test/route': {
                'cli_command': None,
                'sdk_entity': None,
                'gui': True,
                'disposition': 'planned',
            }
        }
    }
    gaps, summary = check_parity(registry)
    assert len(gaps) == 1
    assert 'no ticket' in gaps[0]['reason']


def test_check_passes_on_excluded_route():
    registry = {
        'routes': {
            '/test/route': {
                'cli_command': None,
                'sdk_entity': None,
                'gui': True,
                'disposition': 'excluded',
                'reason': 'Not CLI-appropriate',
            }
        }
    }
    gaps, summary = check_parity(registry)
    assert len(gaps) == 0
    assert summary['excluded'] == 1


def test_check_passes_on_internal_route():
    registry = {
        'routes': {
            '/test/webhook': {
                'cli_command': None,
                'sdk_entity': None,
                'gui': False,
                'disposition': 'internal',
                'reason': 'Webhook receiver',
            }
        }
    }
    gaps, summary = check_parity(registry)
    assert len(gaps) == 0
    assert summary['internal'] == 1


def test_valid_dispositions(registry):
    valid = {'covered', 'planned', 'excluded', 'internal'}
    for route, info in registry['routes'].items():
        assert info['disposition'] in valid, \
            f'{route} has invalid disposition: {info["disposition"]}'
