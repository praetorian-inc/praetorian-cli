from types import SimpleNamespace

import pytest

from praetorian_cli.sdk.entities.search import Search as SDKSearch
from praetorian_cli.ui import entity_resolver
from praetorian_cli.ui.entity_resolver import resolve_entity_reference


class Search:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def fulltext(self, value, kind=None, limit=25):
        self.calls.append(('fulltext', value, kind, limit))
        return list(self.results), None

    def by_term(self, value, kind, pages=1):
        self.calls.append(('by_term', value, kind, pages))
        return [], None


def _sdk(results):
    return SimpleNamespace(search=Search(results))


def test_fulltext_search_reads_only_one_bounded_page(monkeypatch):
    search = SDKSearch(SimpleNamespace())
    calls = []
    monkeypatch.setattr(
        search,
        'by_query',
        lambda query, pages=1: calls.append((query.to_dict(), pages)) or ([], None),
    )

    search.fulltext('database', kind='asset', limit=25)

    query, pages = calls[0]
    assert pages == 1
    assert query['limit'] == 25


def test_field_search_builds_or_query_across_display_fields(monkeypatch):
    search = SDKSearch(SimpleNamespace())
    calls = []
    monkeypatch.setattr(
        search,
        'by_query',
        lambda query, pages=1: calls.append((query.to_dict(), pages)) or ([], None),
    )

    search.by_fields('portal', 'webapplication', ('key', 'name'), limit=25)

    query, pages = calls[0]
    assert pages == 1
    assert query['node']['labels'] == ['WebApplication']
    assert query['filters'][0]['operator'] == 'OR'
    assert [
        condition['field'] for condition in query['filters'][0]['value']
    ] == ['key', 'name']


def test_full_entity_key_is_a_deterministic_fast_path():
    sdk = _sdk([])

    key = resolve_entity_reference(
        sdk,
        '#asset#example.com#10.0.0.5',
        'asset',
    )

    assert key == '#asset#example.com#10.0.0.5'
    assert sdk.search.calls == []


def test_full_entity_key_must_match_expected_type():
    with pytest.raises(ValueError, match='Expected a risk key'):
        resolve_entity_reference(
            _sdk([]),
            '#asset#example.com#10.0.0.5',
            'risk',
        )


def test_unique_friendly_value_resolves_to_canonical_key():
    sdk = _sdk([{
        'key': '#asset#internal.example#10.0.0.5',
        'dns': 'internal.example',
        'identifier': '10.0.0.5',
    }])

    key = resolve_entity_reference(
        sdk,
        '10.0.0.5',
        'asset',
        interactive=False,
    )

    assert key == '#asset#internal.example#10.0.0.5'


def test_exact_field_match_wins_over_other_fulltext_results():
    sdk = _sdk([
        {'key': '#asset#one#10.0.0.5', 'dns': 'one.example'},
        {'key': '#asset#exact#10.0.0.8', 'dns': 'database.example'},
    ])

    key = resolve_entity_reference(
        sdk,
        'database.example',
        'asset',
        interactive=False,
    )

    assert key == '#asset#exact#10.0.0.8'


def test_ambiguous_noninteractive_reference_fails_closed():
    sdk = _sdk([
        {'key': '#risk#one#cve-1', 'name': 'cve-1'},
        {'key': '#risk#two#cve-1', 'name': 'cve-1'},
    ])

    with pytest.raises(ValueError, match='matches multiple risk records'):
        resolve_entity_reference(
            sdk,
            'cve-1',
            'risk',
            interactive=False,
        )


def test_field_search_resolves_entities_without_fulltext_index():
    class FieldSearch(Search):
        def by_fields(self, value, kind, fields, limit=25):
            self.calls.append(('by_fields', value, kind, fields, limit))
            return [{
                'key': '#repository#https://git.example/project#project',
                'name': 'project',
                'url': 'https://git.example/project',
            }], None

    sdk = SimpleNamespace(search=FieldSearch([]))

    key = resolve_entity_reference(
        sdk,
        'https://git.example/project',
        'repository',
        interactive=False,
    )

    assert key == '#repository#https://git.example/project#project'
    assert sdk.search.calls[1][0] == 'by_fields'


def test_search_transport_failure_is_not_reported_as_entity_absence():
    class BrokenSearch:
        def fulltext(self, *_args, **_kwargs):
            raise RuntimeError('search unavailable')

        def by_fields(self, *_args, **_kwargs):
            raise RuntimeError('search unavailable')

        def by_term(self, *_args, **_kwargs):
            raise RuntimeError('search unavailable')

    sdk = SimpleNamespace(search=BrokenSearch())

    with pytest.raises(RuntimeError, match='Guard entity search is unavailable'):
        resolve_entity_reference(
            sdk,
            'internal.example',
            'asset',
            interactive=False,
        )


def test_ambiguous_interactive_reference_uses_selector(monkeypatch):
    sdk = _sdk([
        {'key': '#asset#one#10.0.0.5', 'name': 'shared'},
        {'key': '#asset#two#10.0.0.8', 'name': 'shared'},
    ])
    monkeypatch.setattr(
        entity_resolver,
        'select_entity_keys',
        lambda *_args, **_kwargs: ['#asset#two#10.0.0.8'],
    )

    key = resolve_entity_reference(
        sdk,
        'shared',
        'asset',
        interactive=True,
    )

    assert key == '#asset#two#10.0.0.8'
