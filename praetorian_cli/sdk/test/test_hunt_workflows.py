from io import StringIO

from rich.console import Console

from praetorian_cli.ui.hunt_workflows import (
    WorkflowBrowser,
    browse_hunt_workflows,
    format_hunt_workflows,
)


def test_workflow_formatter_renders_iterations_steps_and_dispatches():
    runs = [
        {
            'run_id': 'run-old',
            'definition': 'hunt',
            'status': 'completed',
            'created': '2026-01-01T01:00:00Z',
            'steps': [{
                'name': 'target-selection',
                'title': 'Target Selection',
                'kind': 'agent',
                'status': 'completed',
                'output': '{"target_dns":"old.example"}',
            }],
        },
        {
            'run_id': 'run-new',
            'definition': 'hunt',
            'status': 'running',
            'created': '2026-01-01T02:00:00Z',
            'endpoint_required': True,
            'endpoint_id': 'endpoint-1',
            'total_tokens_spent': 42,
            'steps': [
                {
                    'name': 'inject-memory-context',
                    'title': 'Memory Context',
                    'kind': 'func',
                    'status': 'completed',
                    'output': '{"memory":{"items":[{}],"status_counts":{"open":1}}}',
                },
                {
                    'name': 'expand-dispatches',
                    'title': 'Dispatch Planning',
                    'kind': 'expansion',
                    'status': 'completed',
                },
                {
                    'name': 'dispatch-0-romulus-agent',
                    'title': 'Romulus',
                    'kind': 'agent',
                    'status': 'persisting',
                    'expanded_by': 'expand-dispatches',
                    'output': 'Testing the selected service. More detail follows.',
                    'queued_at': '2026-01-01T02:00:00Z',
                    'completed_at': '2026-01-01T02:00:05Z',
                },
            ],
        },
    ]

    rendered = format_hunt_workflows(runs)

    assert rendered.index('Iteration 2') < rendered.index('Iteration 1')
    assert 'endpoint-1' in rendered
    assert '42 tokens' in rendered
    assert 'Memory Context' in rendered
    assert '1 memory items (1 open)' in rendered
    assert '↳ Romulus' in rendered
    assert 'Testing the selected service' in rendered
    assert '5s' in rendered
    assert 'Target Selection' in rendered
    assert 'Selected old.example' in rendered
    assert 'More detail follows' not in rendered


def test_workflow_browser_moves_and_toggles_selected_iteration():
    runs = [
        {'run_id': 'new', 'definition': 'internal-hunt'},
        {'run_id': 'old', 'definition': 'internal-hunt'},
    ]
    browser = WorkflowBrowser(runs)

    assert browser.current['run_id'] == 'new'
    assert browser.current_is_expanded is True

    browser.move(1)
    assert browser.current['run_id'] == 'old'
    assert browser.current_is_expanded is False

    browser.toggle()
    assert browser.current_is_expanded is True
    browser.collapse()
    assert browser.current_is_expanded is False
    browser.expand()
    assert browser.current_is_expanded is True


def test_workflow_browser_navigates_only_chat_steps_and_restores_state():
    runs = [{
        'run_id': 'run-1',
        'steps': [
            {'name': 'setup'},
            {'name': 'agent-one', 'conversation_id': 'conversation-one'},
            {'name': 'cleanup'},
            {'name': 'agent-two', 'conversation_id': 'conversation-two'},
        ],
    }]
    browser = WorkflowBrowser(runs)

    assert browser.current_step_index == 1
    assert browser.current_conversation_id == 'conversation-one'
    assert browser.move_step(1) is True
    assert browser.current_step_index == 3
    assert browser.current_conversation_id == 'conversation-two'

    before = (browser.cursor, set(browser.expanded), dict(browser.step_cursors))
    opened = []
    assert browser.activate(opened.append) is True
    assert opened == ['conversation-two']
    assert (browser.cursor, browser.expanded, browser.step_cursors) == before
    assert 'selection restored' in browser.notice

    def unavailable(_conversation_id):
        raise PermissionError('conversation is unavailable')

    assert browser.activate(unavailable) is False
    assert (browser.cursor, browser.expanded, browser.step_cursors) == before
    assert 'Unable to open conversation conversation-two' in browser.notice


def test_workflow_steps_without_conversations_are_clearly_non_actionable():
    browser = WorkflowBrowser([{
        'run_id': 'run-1',
        'steps': [{'name': 'setup'}],
    }])

    assert browser.current_step is None
    assert browser.move_step(1) is False
    assert browser.activate(lambda _conversation_id: None) is False
    assert browser.notice == 'This workflow has no chat-enabled steps.'

    rendered = format_hunt_workflows(browser.runs)
    assert '— no conversation' in rendered
    assert 'Workflow conversation IDs' not in rendered


def test_workflow_browser_falls_back_to_static_output_without_tty():
    output = StringIO()
    console = Console(file=output, width=100, color_system=None)

    browse_hunt_workflows(console, [{
        'run_id': 'run-1',
        'definition': 'internal-hunt',
        'status': 'running',
        'created': '2026-01-01T00:00:00Z',
        'steps': [{
            'name': 'dispatch-agent',
            'conversation_id': '11111111-2222-4333-8444-555555555555',
        }],
    }])

    rendered = output.getvalue()
    assert 'Hunt workflow timeline' in rendered
    assert 'internal-hunt' in rendered
    assert 'Workflow conversation IDs · scriptable' in rendered
    assert (
        'conversation_id=11111111-2222-4333-8444-555555555555'
        in rendered
    )


def test_workflow_formatter_handles_empty_and_invalid_timestamps():
    assert 'No workflow runs found for this Hunt.' in format_hunt_workflows([])

    rendered = format_hunt_workflows([{
        'run_id': 'run-1',
        'status': 'queued',
        'created': 'not-a-date',
        'steps': [],
    }])

    assert 'Iteration 1' in rendered
    assert 'No workflow steps recorded.' in rendered
