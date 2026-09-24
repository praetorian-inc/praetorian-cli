from types import SimpleNamespace

from click.testing import CliRunner

from praetorian_cli.handlers.hunt import hunt
from praetorian_cli.sdk.model.aegis import Agent
from praetorian_cli.ui.hunt_defaults import DEFAULT_FINISH_CRITERIA


ENDPOINT_ID = '11111111-1111-4111-8111-111111111111'
SCOPE = '#asset#internal.example#10.0.0.5'


class FakeHunts:
    def __init__(self):
        self.create_calls = []
        self.hunt = None
        self.endpoint_status = {'sessions': [], 'tasks': []}
        self.workflow_runs = []
        self.conversations = []
        self.interactions = []
        self.interaction_calls = []
        self.root_conversations = []
        self.findings = []
        self.cost_status = {
            'total': {'cost': 0, 'total_tokens': 0},
            'by_model': [],
            'currency': 'USD',
        }
        self.memory_items = []
        self.memory_content = {}
        self.memory_calls = []
        self.log = ''

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {'uuid': 'hunt-1', **kwargs}

    def get(self, _uuid):
        return self.hunt

    def endpoint_execution_status(self, _hunt):
        return self.endpoint_status

    def get_cost(self, _hunt_id):
        return self.cost_status

    def list_root_conversations(self, _hunt_id):
        return list(self.root_conversations), None

    def list_workflow_runs(self, _hunt_id):
        return list(self.workflow_runs), None

    def list_conversations(self, _hunt_id):
        return list(self.conversations), None

    def list_interactions(self, hunt_id, status='pending'):
        self.interaction_calls.append((hunt_id, status))
        return list(self.interactions)

    def list_findings(self, _hunt_id, pages=1):
        return list(self.findings), None

    def list_memory(self, _hunt_id):
        return list(self.memory_items), None

    def get_memory(self, _hunt_id, title):
        return self.memory_content[title]

    def save_memory(self, hunt_id, title, content):
        self.memory_calls.append(('save', hunt_id, title, content))

    def delete_memory(self, hunt_id, title):
        self.memory_calls.append(('delete', hunt_id, title))

    def get_log(self, _hunt_id):
        return self.log


class FakeAssets:
    def __init__(self):
        self.candidates = []
        self.calls = []

    def list_hunt_scope(self, **kwargs):
        self.calls.append(kwargs)
        return list(self.candidates), None


class FakeRisks:
    def get(self, key, details=False, evidence='off'):
        return {'key': key, 'status': 'OH', 'statusLabel': 'Open High'}


class FakeSearch:
    def __init__(self):
        self.results = []

    def fulltext(self, _value, kind=None, limit=25):
        return list(self.results), None

    def by_fields(self, _value, _kind, _fields, limit=25):
        return [], None

    def by_term(self, _value, _kind, pages=1):
        return [], None


class FakeConversations:
    def __init__(self):
        self.sent = []
        self.transcripts = {}

    def send_message(self, conversation_id, message):
        self.sent.append((conversation_id, message))
        return {'response': {'success': True}}

    def get(self, conversation_id):
        return self.transcripts.get(conversation_id, {'messages': []})


class FakeAegis:
    def __init__(self, agents):
        self.agents = agents

    def list_hunt_endpoints(self):
        return list(self.agents)


def _endpoint(hostname='aegis-internal', endpoint_id=ENDPOINT_ID):
    return Agent.from_endpoint_dict({
        'endpointId': endpoint_id,
        'kind': 'aegis',
        'hostname': hostname,
    })


def _sdk(agents=None):
    return SimpleNamespace(
        hunts=FakeHunts(),
        conversations=FakeConversations(),
        search=FakeSearch(),
        assets=FakeAssets(),
        risks=FakeRisks(),
        aegis=FakeAegis(agents if agents is not None else [_endpoint()]),
    )


def _launch_args(*extra):
    return [
        'launch',
        '--prompt', 'Assess internal services',
        '--scope', SCOPE,
        *extra,
    ]


def test_internal_hunt_cli_sends_confirmed_endpoint_contract():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args(
            '--internal',
            '--endpoint', ENDPOINT_ID,
            '--confirm-endpoint',
        ),
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls == [{
        'prompt': 'Assess internal services',
        'expires_hours': 24,
        'agent': 'hannibal',
        'scope': [SCOPE],
        'scope_level': 'normal',
        'aggressiveness': 'balanced',
        'finish_criteria': DEFAULT_FINISH_CRITERIA,
        'user_guardrails': '',
        'custom_tag': '',
        'model_tier_override': None,
        'credential_ids': None,
        'endpoint_required': True,
        'endpoint_id': ENDPOINT_ID,
        'endpoint_confirmed': True,
    }]


def test_internal_hunt_cli_resolves_friendly_scope_value():
    sdk = _sdk()
    sdk.search.results = [{
        'key': SCOPE,
        'dns': 'internal.example',
        'identifier': '10.0.0.5',
    }]

    result = CliRunner().invoke(
        hunt,
        [
            'launch',
            '--prompt', 'Assess internal services',
            '--scope', '10.0.0.5',
            '--internal',
            '--endpoint', ENDPOINT_ID,
            '--confirm-endpoint',
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls[0]['scope'] == [SCOPE]


def test_internal_hunt_cli_discovers_scope_and_sends_ui_launch_fields(
    monkeypatch,
):
    sdk = _sdk()
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda _console, config, *_args: (dict(config), True),
    )
    sdk.assets.candidates = [{
        'key': SCOPE,
        'dns': 'internal.example',
        'identifier': '10.0.0.5',
        'class': 'ipv4',
        'status': 'A',
    }]

    result = CliRunner().invoke(
        hunt,
        [
            'launch',
            '--prompt', 'Assess internal services',
            '--internal',
            '--endpoint', ENDPOINT_ID,
            '--confirm-endpoint',
            '--select-scope',
            '--finish-criteria', 'Stop after critical compromise',
            '--guardrails', 'Do not authenticate',
            '--custom-tag', 'Internal-Q4',
            '--model-tier', 'experimental',
            '--credential', 'ad-1',
            '--credential', '#credential#integration#web-auth#web-1',
        ],
        obj=sdk,
        input='1\ndone\n',
    )

    assert result.exit_code == 0, result.output
    assert SCOPE in sdk.hunts.create_calls[0]['scope']
    assert sdk.hunts.create_calls[0]['finish_criteria'] == (
        'Stop after critical compromise'
    )
    assert sdk.hunts.create_calls[0]['user_guardrails'] == 'Do not authenticate'
    assert sdk.hunts.create_calls[0]['custom_tag'] == 'Internal-Q4'
    assert sdk.hunts.create_calls[0]['model_tier_override'] == 'experimental'
    assert sdk.hunts.create_calls[0]['credential_ids'] == [
        'ad-1',
        '#credential#integration#web-auth#web-1',
    ]
    assert sdk.assets.calls == [{
        'agent': 'hannibal',
        'internal': True,
        'pages': 1,
    }]
    assert 'internal.example' in result.output


def test_internal_hunt_cli_confirmation_names_offline_no_fallback_policy(
    monkeypatch,
):
    sdk = _sdk()
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda _console, config, *_args: (dict(config), True),
    )

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--endpoint', 'aegis-internal'),
        obj=sdk,
        input='y\n',
    )

    assert result.exit_code == 0, result.output
    assert 'aegis-internal' in result.output
    assert ENDPOINT_ID in result.output
    assert 'offline' in result.output
    assert 'waits without Guard compute fallback' in result.output
    assert sdk.hunts.create_calls[0]['endpoint_confirmed'] is True


def test_internal_hunt_cli_can_select_an_authorized_v2_endpoint(monkeypatch):
    second_id = '22222222-2222-4222-8222-222222222222'
    sdk = _sdk([_endpoint('first'), _endpoint('second', second_id)])
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda _console, config, *_args: (dict(config), True),
    )

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal'),
        obj=sdk,
        input='2\ny\n',
    )

    assert result.exit_code == 0, result.output
    assert 'Authorized Aegis v2 endpoints' in result.output
    assert sdk.hunts.create_calls[0]['endpoint_id'] == second_id


def test_internal_hunt_endpoint_id_takes_priority_over_matching_hostname():
    second_id = '22222222-2222-4222-8222-222222222222'
    sdk = _sdk([
        _endpoint(second_id, ENDPOINT_ID),
        _endpoint('second', second_id),
    ])

    result = CliRunner().invoke(
        hunt,
        _launch_args(
            '--internal',
            '--endpoint', second_id,
            '--confirm-endpoint',
        ),
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls[0]['endpoint_id'] == second_id


def test_internal_hunt_cli_rejects_endpoint_options_without_internal_mode():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args('--endpoint', ENDPOINT_ID),
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'require --internal' in result.output
    assert sdk.hunts.create_calls == []


def test_hunt_cli_rejects_run_credential_without_internal_mode():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        _launch_args('--credential', 'ad-1'),
        obj=sdk,
    )

    assert result.exit_code != 0
    assert '--credential requires --internal' in result.output


def test_internal_hunt_cli_requires_hannibal_and_scope():
    sdk = _sdk()

    wrong_agent = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--agent', 'hannibal-webapp'),
        obj=sdk,
    )
    no_scope = CliRunner().invoke(
        hunt,
        ['launch', '--prompt', 'test', '--internal'],
        obj=sdk,
    )

    assert wrong_agent.exit_code != 0
    assert 'requires the hannibal infrastructure agent' in wrong_agent.output
    assert no_scope.exit_code != 0
    assert 'Specific Hunts require at least one --scope' in no_scope.output
    assert sdk.hunts.create_calls == []


def test_internal_hunt_cli_rejects_legacy_aegis_agent():
    sdk = _sdk([Agent(client_id='C.legacy', hostname='legacy')])

    result = CliRunner().invoke(
        hunt,
        _launch_args('--internal', '--endpoint', 'C.legacy'),
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'No authorized Aegis v2 endpoints' in result.output
    assert sdk.hunts.create_calls == []


def test_hunt_findings_lists_filtered_vulnerabilities():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1'}
    sdk.hunts.findings = [
        {
            'key': '#risk#db#sql',
            'dns': 'db.example',
            'title': 'SQL injection',
            'status': 'OH',
            'statusLabel': 'Open High',
        },
        {
            'key': '#risk#web#headers',
            'title': 'Missing headers',
            'status': 'TM',
            'statusLabel': 'Detected Medium',
        },
    ]

    result = CliRunner().invoke(
        hunt,
        ['findings', 'hunt-1', '--severity', 'high'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'SQL injection' in result.output
    assert 'Missing headers' not in result.output


def test_hunt_memory_lists_reads_saves_and_deletes_items():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1'}
    sdk.hunts.memory_items = [{
        'title': 'target.md',
        'bytes': 12,
        'updated': '2026-01-01T00:00:00Z',
    }]
    sdk.hunts.memory_content['target.md'] = 'remember this target'

    listed = CliRunner().invoke(hunt, ['memory', 'hunt-1'], obj=sdk)
    viewed = CliRunner().invoke(
        hunt,
        ['memory', 'hunt-1', '--item', 'target.md'],
        obj=sdk,
    )
    saved = CliRunner().invoke(
        hunt,
        ['memory', 'hunt-1', '--item', 'target.md', '--content', 'updated'],
        obj=sdk,
    )
    deleted = CliRunner().invoke(
        hunt,
        ['memory', 'hunt-1', '--item', 'target.md', '--delete', '--yes'],
        obj=sdk,
    )

    assert listed.exit_code == viewed.exit_code == saved.exit_code == deleted.exit_code == 0
    assert 'target.md' in listed.output
    assert 'remember this target' in viewed.output
    assert sdk.hunts.memory_calls == [
        ('save', 'hunt-1', 'target.md', 'updated'),
        ('delete', 'hunt-1', 'target.md'),
    ]


def test_hunt_memory_without_static_options_delegates_to_browser(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1'}
    calls = []
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.browse_hunt_memory',
        lambda console, hunts, hunt_id: calls.append((hunts, hunt_id)),
    )

    result = CliRunner().invoke(hunt, ['memory', 'hunt-1'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert calls == [(sdk.hunts, 'hunt-1')]


def test_hunt_open_launches_unified_fullscreen_interface(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    calls = []
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_hunt_open',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.run_hunt_open',
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = CliRunner().invoke(
        hunt,
        ['open', 'hunt-1'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert calls[0][0] == (sdk, 'hunt-1')
    assert calls[0][1]['initial_hunt'] == sdk.hunts.hunt
    assert 'refresh_interval' not in calls[0][1]
    assert callable(calls[0][1]['confirm_stop'])
    assert callable(calls[0][1]['review_interactions'])


def test_fullscreen_hunt_commands_do_not_offer_auto_refresh_interval():
    runner = CliRunner()

    open_help = runner.invoke(hunt, ['open', '--help'])
    chat_help = runner.invoke(hunt, ['chat', '--help'])

    assert open_help.exit_code == 0
    assert chat_help.exit_code == 0
    assert '--interval' not in open_help.output
    assert '--interval' not in chat_help.output


def test_hunt_open_requires_tty_without_changing_static_commands(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_hunt_open',
        lambda: False,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.run_hunt_open',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError('non-TTY invocation must not start the app')
        ),
    )

    result = CliRunner().invoke(hunt, ['open', 'hunt-1'], obj=sdk)

    assert result.exit_code != 0
    assert 'requires an interactive terminal' in result.output


def test_hunt_log_displays_summary_log():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1'}
    sdk.hunts.log = '[iteration-complete] confirmed SMB'

    result = CliRunner().invoke(hunt, ['log', 'hunt-1'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert 'Hannibal Hunt Log' in result.output
    assert 'confirmed SMB' in result.output


def test_hunt_log_follow_stops_cleanly_on_interrupt(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1'}
    sdk.hunts.log = '[iteration-complete] confirmed SMB'
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.time.sleep',
        lambda _interval: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = CliRunner().invoke(
        hunt,
        ['log', 'hunt-1', '--follow', '--interval', '1'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'Stopped following Hunt log' in result.output


def test_hunt_chat_uses_fullscreen_live_view_in_an_interactive_terminal(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    calls = []
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_live_hunt_chat',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.run_live_hunt_chat',
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = CliRunner().invoke(
        hunt,
        ['chat', 'hunt-1', '--conversation', 'root-prefix'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert calls[0][0] == (sdk, 'hunt-1')
    assert calls[0][1]['requested_id'] == 'root-prefix'
    assert 'refresh_interval' not in calls[0][1]
    assert callable(calls[0][1]['review_interactions'])
    assert sdk.hunts.conversations == []


def test_hunt_chat_queues_guidance_for_active_iteration():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    sdk.hunts.conversations = [{
        'uuid': 'conversation-1',
        'status': 'active',
        'parent_id': 'self',
        'created': '2026-01-01T02:00:00Z',
    }]
    sdk.conversations.transcripts['conversation-1'] = {
        'messages': [{
            'role': 'chariot',
            'content': 'Testing the selected target.',
            'timestamp': '2026-01-01T02:01:00Z',
        }],
    }

    result = CliRunner().invoke(
        hunt,
        ['chat', 'hunt-1', '--message', 'Focus on SMB'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.conversations.sent == [('conversation-1', 'Focus on SMB')]
    assert 'Hannibal Hunt Chat' in result.output
    assert 'Testing the selected target.' in result.output
    assert 'Guidance queued' in result.output


def test_hunt_interactions_lists_pending_requests_without_model_text():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    sdk.hunts.interactions = [{
        'conversationId': 'child-conversation',
        'requestId': 'request-1',
        'kind': 'credential',
        'status': 'pending',
        'request': 'MODEL TEXT WITH VALUE-THAT-MUST-NOT-RENDER',
        'fields': ['username', 'password'],
    }]

    result = CliRunner().invoke(
        hunt,
        ['interactions', 'hunt-1'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.interaction_calls == [('hunt-1', 'pending')]
    assert 'Pending Hunt interactions' in result.output
    assert 'username' in result.output
    assert 'password' in result.output
    assert 'VALUE-THAT-MUST-NOT-RENDER' not in result.output


def test_hunt_interaction_watch_preserves_non_tty_read_only_behavior(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    sdk.hunts.interactions = [{
        'conversationId': 'conversation-1',
        'requestId': 'approval-1',
        'kind': 'approval',
        'status': 'pending',
    }]
    monkeypatch.setattr(
        'praetorian_cli.ui.hunt_chat.time.sleep',
        lambda _interval: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = CliRunner().invoke(
        hunt,
        ['interactions', 'hunt-1', '--watch', '--interval', '1'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'Watching read-only' in result.output
    assert 'Stopped watching Hunt interactions' in result.output


def test_hunt_interaction_watch_prints_new_pending_requests(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    pending = [{
        'conversationId': 'child-conversation',
        'requestId': 'credential-1',
        'kind': 'credential',
        'status': 'pending',
        'fields': ['token'],
    }]
    snapshots = iter([[], pending])
    sdk.hunts.list_interactions = lambda *_args, **_kwargs: next(snapshots)
    sleeps = iter([None, KeyboardInterrupt()])

    def sleep(_interval):
        outcome = next(sleeps)
        if isinstance(outcome, BaseException):
            raise outcome

    monkeypatch.setattr('praetorian_cli.ui.hunt_chat.time.sleep', sleep)

    result = CliRunner().invoke(
        hunt,
        ['interactions', 'hunt-1', '--watch', '--interval', '1'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'New pending Hunt interactions' in result.output
    assert 'credential-1' in result.output
    assert 'Stopped watching Hunt interactions' in result.output


def test_hunt_chat_rejects_guidance_when_no_iteration_is_active():
    sdk = _sdk()
    sdk.hunts.hunt = {'uuid': 'hunt-1', 'status': 'active'}
    sdk.hunts.conversations = [{
        'uuid': 'conversation-1',
        'status': 'idle',
        'parent_id': 'self',
        'created': '2026-01-01T02:00:00Z',
    }]

    result = CliRunner().invoke(
        hunt,
        ['chat', 'hunt-1', '--message', 'Focus on SMB'],
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'active Hunt iteration' in result.output
    assert sdk.conversations.sent == []


def test_hunt_status_can_render_workflow_iterations():
    sdk = _sdk()
    sdk.hunts.hunt = {
        'uuid': 'hunt-1',
        'status': 'active',
        'agent': 'hannibal',
    }
    sdk.hunts.workflow_runs = [{
        'run_id': 'run-1',
        'definition': 'hunt',
        'status': 'running',
        'created': '2026-01-01T02:00:00Z',
        'steps': [{
            'name': 'target-selection',
            'title': 'Target Selection',
            'kind': 'agent',
            'status': 'running',
        }],
    }]

    result = CliRunner().invoke(
        hunt,
        ['status', 'hunt-1', '--workflows'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert 'Hunt workflow timeline' in result.output
    assert 'ITERATIONS' in result.output
    assert 'Iteration 1' in result.output
    assert 'Target Selection' in result.output
    assert 'AGENT' in result.output
    assert 'RUNNING' in result.output


def test_hunt_status_renders_operational_overview_with_bounded_summaries():
    sdk = _sdk()
    sdk.hunts.hunt = {
        'uuid': 'hunt-1',
        'status': 'active',
        'agent': 'hannibal',
        'iterationCount': 7,
        'findingsCount': 2,
        'expiresAt': '2099-01-01T00:00:00Z',
        'scope': [
            f'#asset#host-{index}.example.com#10.0.0.{index}'
            for index in range(100)
        ],
    }
    sdk.hunts.root_conversations = [
        {'uuid': f'conversation-{index}', 'title': f'Iteration agent {index}'}
        for index in range(100)
    ]
    sdk.hunts.findings = [
        {'status': 'OH', 'statusLabel': 'Open High'},
        {'status': 'TC', 'statusLabel': 'Triaged Critical'},
    ]
    sdk.hunts.cost_status = {
        'total': {'cost': 0, 'total_tokens': 150},
        'by_model': [],
        'currency': 'USD',
    }

    result = CliRunner().invoke(hunt, ['status', 'hunt-1'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert '"rootAgents": 100' in result.output
    assert '"iterations": 7' in result.output
    assert '"highestSeverity": "Critical"' in result.output
    assert '"projectedCost": "$0.00"' in result.output
    assert '"remaining":' in result.output
    assert 'host-0.example.com (10.0.0.0)' in result.output
    assert 'host-5.example.com' not in result.output
    assert '(+95 more)' in result.output
    assert 'total_tokens' not in result.output


def test_hunt_status_workflow_step_opens_exact_live_conversation(monkeypatch):
    sdk = _sdk()
    sdk.hunts.hunt = {
        'uuid': 'hunt-1',
        'status': 'active',
        'agent': 'hannibal',
    }
    sdk.hunts.workflow_runs = [{
        'run_id': 'run-1',
        'steps': [{
            'name': 'dispatch-agent',
            'conversation_id': 'conversation-exact',
        }],
    }]
    calls = []

    def open_selected(_console, runs, *, open_conversation):
        assert runs == sdk.hunts.workflow_runs
        open_conversation(runs[0]['steps'][0]['conversation_id'])

    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.browse_hunt_workflows',
        open_selected,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.run_live_hunt_chat',
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = CliRunner().invoke(
        hunt,
        ['status', 'hunt-1', '--workflows'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert calls[0][0] == (sdk, 'hunt-1')
    assert calls[0][1]['requested_id'] == 'conversation-exact'
    assert calls[0][1]['exact_requested_id'] is True
    assert callable(calls[0][1]['review_interactions'])


def test_hunt_status_includes_internal_execution_placement():
    sdk = _sdk()
    sdk.hunts.hunt = {
        'uuid': 'hunt-1',
        'status': 'active',
        'agent': 'hannibal',
        'endpointRequired': True,
        'endpointId': ENDPOINT_ID,
        'currentWorkflowRunId': 'workflow-1',
    }
    sdk.hunts.endpoint_status = {
        'sessions': [],
        'tasks': [{
            'endpointId': ENDPOINT_ID,
            'taskId': 'task-1',
            'jobKey': '#job#1',
            'capability': 'portscan',
            'target': SCOPE,
            'state': 'Ready',
            'phase': 'waiting_for_endpoint',
            'endpointConnectionState': 'not_connected',
        }],
    }

    result = CliRunner().invoke(hunt, ['status', 'hunt-1'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert '"endpointRequired": true' in result.output
    assert f'"endpointId": "{ENDPOINT_ID}"' in result.output
    assert '"currentWorkflowRunId": "workflow-1"' in result.output
    assert 'Waiting for assigned endpoint (no compute fallback)' in result.output
