from praetorian_cli.sdk.entities.assets import Assets
from praetorian_cli.ui import entity_selector
from praetorian_cli.ui.entity_selector import (
    EntitySelector,
    filter_entities,
    parse_selection,
    select_entity_keys,
)


class Search:
    def __init__(self):
        self.calls = []

    def by_query(self, query, pages):
        self.calls.append((query.to_dict(), pages))
        return [], None


def test_internal_hunt_scope_query_matches_ui_fences():
    search = Search()

    Assets(type('API', (), {'search': search})()).list_hunt_scope(
        agent='hannibal',
        internal=True,
        pages=1,
    )

    query, pages = search.calls[0]
    assert pages == 1
    assert query['node']['labels'] == ['Asset']
    filters = query['node']['filters']
    assert {'field': 'status', 'operator': 'STARTS WITH', 'value': 'A', 'not': False} in filters
    assert {'field': 'class', 'operator': 'IN', 'value': [['ipv4', 'cidr']], 'not': False} in filters
    assert {'field': 'isInternal', 'operator': '=', 'value': True, 'not': False} in filters


def test_hunt_scope_search_uses_asset_fulltext_index():
    search = Search()

    Assets(type('API', (), {'search': search})()).list_hunt_scope(
        agent='hannibal',
        internal=True,
        search='database 10.0.0.8',
    )

    query, _ = search.calls[0]
    assert query['node']['search'] == 'database 10.0.0.8'


def test_hunt_scope_query_can_resume_at_a_later_page():
    search = Search()

    Assets(type('API', (), {'search': search})()).list_hunt_scope(
        agent='hannibal',
        internal=True,
        page=7,
    )

    query, _ = search.calls[0]
    assert query['page'] == 7
    assert query['limit'] == 200


def test_llm_hunt_scope_queries_active_llm_webapplications():
    search = Search()

    Assets(type('API', (), {'search': search})()).list_hunt_scope(
        agent='hannibal-llm',
    )

    query, _ = search.calls[0]
    assert query['node']['labels'] == ['WebApplication']
    assert {'field': 'isLLM', 'operator': '=', 'value': True, 'not': False} in query['node']['filters']


def test_webapplication_hunt_scope_searches_display_fields():
    search = Search()

    Assets(type('API', (), {'search': search})()).list_hunt_scope(
        agent='hannibal-webapp',
        search='portal.example',
    )

    query, _ = search.calls[0]
    search_filter = query['filters'][0]
    assert search_filter['operator'] == 'OR'
    assert {
        condition['field'] for condition in search_filter['value']
    } == {'key', 'name', 'primary_url', 'identifier', 'domain'}
    assert all(
        condition['value'] == 'portal.example'
        for condition in search_filter['value']
    )


def test_interactive_selector_moves_filters_and_preserves_selection():
    entities = [
        {'key': '#asset#alpha#10.0.0.1', 'dns': 'alpha'},
        {'key': '#asset#beta#10.0.0.2', 'dns': 'beta'},
    ]
    searches = []

    def search_entities(query, offset):
        searches.append((query, offset))
        return ([{'key': '#asset#gamma#10.0.0.3', 'dns': 'gamma'}], None)

    selector = EntitySelector(
        entities,
        search_entities=search_entities,
        next_offset=None,
    )
    selector.move(1)
    selector.toggle_current()
    selector.begin_search()
    selector.clear_search()
    selector.append_search('gamma')
    selector.apply_search()

    assert selector.current['dns'] == 'gamma'
    assert selector.selected_keys == ['#asset#beta#10.0.0.2']
    assert searches == [('gamma', None)]


def test_interactive_selector_arrow_navigation_loads_next_server_page():
    first = [{'key': '#asset#one#10.0.0.1', 'dns': 'one'}]
    second = [{'key': '#asset#two#10.0.0.2', 'dns': 'two'}]
    selector = EntitySelector(
        first,
        search_entities=lambda query, offset: (second, None),
        next_offset=1,
    )

    selector.move(1)

    assert selector.page_index == 1
    assert selector.current == second[0]
    selector.move(-1)
    assert selector.page_index == 0
    assert selector.current == first[0]


def test_entity_selector_disambiguates_duplicate_labels_with_canonical_keys(monkeypatch):
    from io import StringIO
    from rich.console import Console

    output = StringIO()
    duplicate_label_entities = [
        {
            'key': '#asset#group-one#10.0.0.5',
            'dns': 'shared.example',
            'identifier': '10.0.0.5',
        },
        {
            'key': '#asset#group-two#10.0.0.5',
            'dns': 'shared.example',
            'identifier': '10.0.0.5',
        },
        {
            'key': '#asset#group-two#10.0.0.5',
            'dns': 'duplicate-record',
        },
    ]
    monkeypatch.setattr(
        entity_selector.Prompt,
        'ask',
        lambda *_args, **_kwargs: 'q',
    )

    select_entity_keys(
        Console(file=output, width=140, color_system=None),
        duplicate_label_entities,
    )
    rendered = output.getvalue()

    assert '#asset#group-one#10.0.0.5' in rendered
    assert '#asset#group-two#10.0.0.5' in rendered
    assert rendered.count('#asset#group-two#10.0.0.5') == 1


def test_entity_selector_pages_through_visible_chunks_before_server(monkeypatch):
    from io import StringIO
    from rich.console import Console

    entities = [
        {'key': f'#asset#target-{index}#10.0.0.{index}', 'dns': f'target-{index}'}
        for index in range(1, 31)
    ]
    responses = iter(['next', '1', 'done'])
    server_calls = []
    monkeypatch.setattr(
        entity_selector.Prompt,
        'ask',
        lambda *_args, **_kwargs: next(responses),
    )

    selected = select_entity_keys(
        Console(file=StringIO(), width=100),
        entities,
        search_entities=lambda query, offset: server_calls.append(
            (query, offset)
        ) or ([], None),
        next_offset=1,
    )

    assert selected == [entities[25]['key']]
    assert server_calls == []


def test_entity_selector_can_page_without_loading_every_asset(monkeypatch):
    from io import StringIO
    from rich.console import Console

    first = {'key': '#asset#one#10.0.0.1', 'dns': 'one'}
    second = {'key': '#asset#two#10.0.0.2', 'dns': 'two'}
    responses = iter(['next', '1', 'done'])
    calls = []

    def load_page(query, offset):
        calls.append((query, offset))
        return [second], None

    monkeypatch.setattr(
        entity_selector.Prompt,
        'ask',
        lambda *_args, **_kwargs: next(responses),
    )

    selected = select_entity_keys(
        Console(file=StringIO(), width=100),
        [first],
        search_entities=load_page,
        next_offset=1,
    )

    assert selected == [second['key']]
    assert calls == [('', 1)]


def test_entity_selector_filters_without_requiring_full_keys():
    entities = [
        {
            'key': '#asset#internal.example#10.0.0.5',
            'dns': 'internal.example',
            'identifier': '10.0.0.5',
        },
        {
            'key': '#asset#database.example#10.0.0.8',
            'dns': 'database.example',
            'identifier': '10.0.0.8',
        },
    ]

    assert filter_entities(entities, '10.0.0.5') == [entities[0]]
    assert filter_entities(entities, 'database 10.0.0.8') == [entities[1]]
    assert parse_selection('2,1,2', 2) == [1, 0]
