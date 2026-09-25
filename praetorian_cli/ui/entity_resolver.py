import sys

from rich.console import Console

from praetorian_cli.ui.entity_selector import select_entity_keys


SEARCH_FIELDS = {
    'asset': ('key', 'identifier', 'group', 'name', 'dns'),
    'risk': ('key', 'dns', 'name', 'title'),
    'repository': ('key', 'name', 'identifier', 'url'),
    'webapplication': ('key', 'name', 'primary_url', 'identifier', 'domain'),
}
MATCH_FIELDS = (
    'key',
    'dns',
    'name',
    'title',
    'identifier',
    'group',
    'primary_url',
    'url',
)


def resolve_entity_reference(
    sdk,
    value,
    entity_type,
    *,
    interactive=None,
    console=None,
):
    """Resolve a friendly value to one canonical Guard entity key."""
    value = str(value or '').strip()
    entity_label = entity_type or 'entity'
    if not value:
        raise ValueError(f'{entity_label} reference is required')
    if value.startswith('#'):
        if not _key_matches_type(value, entity_type):
            raise ValueError(
                f'Expected a {entity_label} key, got {value!r}.'
            )
        return value

    if interactive is None:
        interactive = sys.stdin.isatty()

    candidates = find_entity_candidates(sdk, value, entity_type)
    exact_matches = [
        candidate for candidate in candidates
        if _is_exact_match(candidate, value)
    ]
    matches = exact_matches or candidates
    if len(matches) == 1:
        return matches[0]['key']
    if not matches:
        raise ValueError(
            f'Could not resolve {value!r} to an existing {entity_label}.'
        )
    if not interactive:
        raise ValueError(_ambiguity_message(value, entity_label, matches))

    console = console or Console()
    selected = select_entity_keys(
        console,
        matches,
        title=f'Select {entity_label}',
        search_entities=lambda query, _offset: find_entity_candidates(
            sdk,
            query,
            entity_type,
        ),
        multiple=False,
    )
    if not selected:
        raise ValueError(f'{entity_label} selection cancelled')
    return selected[0]


def find_entity_candidates(sdk, value, entity_type, limit=25):
    """Find and deduplicate candidates for a friendly entity reference."""
    value = str(value or '').strip()
    search = getattr(sdk, 'search', None)
    if not value or search is None:
        return []

    candidates = []
    failures = []
    for search_kind in _search_kinds(entity_type):
        try:
            candidates.extend(
                _find_candidates_for_kind(
                    sdk,
                    value,
                    search_kind,
                    limit,
                )
            )
        except Exception as exc:
            failures.append(exc)

    unique = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        key = candidate.get('key')
        if key and _key_matches_type(key, entity_type):
            unique.setdefault(key, candidate)
    if unique:
        return list(unique.values())[:limit]
    if failures:
        raise RuntimeError('Guard entity search is unavailable') from failures[-1]
    return []


def _find_candidates_for_kind(sdk, value, search_kind, limit):
    candidates = []
    failures = []
    succeeded = False
    try:
        results, _ = sdk.search.fulltext(
            value,
            kind=search_kind,
            limit=limit,
        )
        candidates.extend(results)
        succeeded = True
    except Exception as exc:
        failures.append(exc)

    if not candidates and search_kind and hasattr(sdk.search, 'by_fields'):
        try:
            results, _ = sdk.search.by_fields(
                value,
                search_kind,
                SEARCH_FIELDS.get(
                    search_kind,
                    ('key', 'name', 'dns', 'identifier'),
                ),
                limit=limit,
            )
            candidates.extend(results)
            succeeded = True
        except Exception as exc:
            failures.append(exc)

    if candidates:
        return candidates
    for field in ('dns', 'name'):
        try:
            results, _ = sdk.search.by_term(
                f'{field}:{value}',
                search_kind,
                pages=1,
            )
            candidates.extend(results)
            succeeded = True
        except Exception as exc:
            failures.append(exc)
    if not candidates and failures and not succeeded:
        raise failures[-1]
    return candidates


def _search_kinds(entity_type):
    if entity_type == 'asset':
        return ('asset', 'webapplication')
    return (entity_type,)


def _key_matches_type(key, entity_type):
    if entity_type is None:
        return key.startswith('#')
    if entity_type == 'asset':
        return key.startswith(('#asset#', '#webapplication#'))
    return key.startswith(f'#{entity_type}#')


def _is_exact_match(candidate, value):
    expected = value.casefold()
    return any(
        str(candidate.get(field) or '').strip().casefold() == expected
        for field in MATCH_FIELDS
    )


def _ambiguity_message(value, entity_type, matches):
    examples = ', '.join(
        str(candidate.get('key'))
        for candidate in matches[:5]
    )
    suffix = '' if len(matches) <= 5 else f', … ({len(matches)} matches)'
    return (
        f'{value!r} matches multiple {entity_type} records: '
        f'{examples}{suffix}. Use a full key or run interactively to choose.'
    )
