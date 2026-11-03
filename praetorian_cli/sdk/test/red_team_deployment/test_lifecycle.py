"""Context-bound lifecycle approval and fail-closed rejection behavior."""

import json

import pytest

from conftest import (
    COMMIT, CONTEXT, ENQUEUED, JOB_ID, PREFIX, SECRET, STATE,
    assert_no_execute, assert_preview_rendered, lifecycle_calls, operation, safe_preview,
)


ACTIONS = [
    ('launch', ['launch', '--desired-id', 'engagement-rt', '--yes'],
     {'action': 'launch', 'desired_id': 'engagement-rt'}),
    ('plan', ['plan', '--config-json', json.dumps(STATE), '--tag', 'v1.2.3', '--force'],
     {'action': 'plan', 'state': STATE, 'tag': 'v1.2.3', 'force': True}),
    ('apply', ['apply', '--config-json', json.dumps(STATE), '--tag', 'v1.2.3', '--force', '--yes'],
     {'action': 'apply', 'state': STATE, 'tag': 'v1.2.3', 'force': True}),
    ('update_collaborators', ['collaborators', '--collaborator', 'first@example.test',
                             '--collaborator', 'second@example.test', '--yes'],
     {'action': 'update_collaborators', 'collaborators': ['first@example.test', 'second@example.test']}),
    ('update_infrastructure_tag', ['tag', '--tag', 'v1.2.3', '--yes'],
     {'action': 'update_infrastructure_tag', 'tag': 'v1.2.3'}),
    ('delete', ['delete', '--force', '--yes'], {'action': 'delete', 'force': True}),
]



@pytest.mark.parametrize('action,args,expected', ACTIONS, ids=[row[0] for row in ACTIONS])
def test_each_action_renders_preview_before_context_bound_execute(api, invoke, action, args, expected):
    api.preview = safe_preview(action)
    api.result = operation(action=action)
    result = invoke(args)
    assert result.exit_code == 0, result.output
    assert_preview_rendered(api.output_before_execute, action)
    calls = lifecycle_calls(api)
    assert [(c['method'], c['target']) for c in calls] == [
        ('POST', PREFIX + 'preview'), ('POST', PREFIX + 'execute'),
    ]
    assert calls[0]['body'] == expected
    assert calls[1]['body'] == expected | {'configuration_context_sha256': CONTEXT}
    assert calls[1]['raw'].count(b'"configuration_context_sha256"') == 1
    assert 'Execute the displayed' not in result.output
    assert '"status": "enqueued"' in result.output
    assert JOB_ID in result.output and ENQUEUED in result.output
    assert SECRET not in result.output
    if action == 'apply':
        assert 'Terraform computes its execution plan during apply' in api.output_before_execute
    if action == 'plan':
        assert all(c['body']['action'] == 'plan' for c in calls)


@pytest.mark.parametrize('args,input', [(['delete'], None), (['delete'], 'y\n'), (['delete', '--force'], 'y\n')])
def test_nonterminal_input_and_force_are_not_approval(api, invoke, args, input):
    result = invoke(args, input=input)
    assert result.exit_code == 2, result.output
    assert_preview_rendered(result.output)
    assert '--yes' in result.output
    assert [(c['method'], c['target']) for c in lifecycle_calls(api)] == [('POST', PREFIX + 'preview')]
    assert_no_execute(api)


@pytest.mark.parametrize('terminal', [(True, False), (False, True)])
def test_both_input_and_output_must_be_terminal_to_prompt(api, invoke, terminal):
    result = invoke(['delete'], input='y\n', terminal=terminal)
    assert result.exit_code == 2, result.output
    assert_preview_rendered(result.output)
    assert 'Execute the displayed' not in result.output
    assert_no_execute(api)


@pytest.mark.parametrize('input,approved', [('\n', False), ('n\n', False), ('y\n', True), ('', False)])
def test_terminal_confirmation_is_default_no_and_eof_aborts(api, invoke, input, approved):
    result = invoke(['delete'], input=input, terminal=True)
    assert_preview_rendered(result.output)
    prompt = 'Execute the displayed delete operation'
    assert prompt in result.output
    assert result.output.index(CONTEXT) < result.output.index(prompt)
    assert '[y/N]' in result.output
    if approved:
        assert result.exit_code == 0, result.output
        assert_preview_rendered(api.output_before_execute)
        assert [c['target'] for c in lifecycle_calls(api)] == [PREFIX + 'preview', PREFIX + 'execute']
    else:
        assert result.exit_code != 0
        assert 'Aborted' in result.output
        assert_no_execute(api)


def test_file_is_read_once_even_if_replaced_after_preview(api, invoke, tmp_path):
    config = tmp_path / 'configuration.json'
    config.write_text(json.dumps(STATE))
    api.preview = safe_preview('apply')
    api.on_preview = lambda: config.write_text('{"nodes": [{"id": "unreviewed"}]}')
    result = invoke(['apply', '--config-file', str(config), '--tag', 'v1.2.3', '--yes'])
    assert result.exit_code == 0, result.output
    calls = lifecycle_calls(api)
    assert calls[0]['body']['state'] == STATE
    assert calls[1]['body'] == calls[0]['body'] | {'configuration_context_sha256': CONTEXT}
    assert 'unreviewed' not in calls[1]['raw'].decode()
    assert SECRET not in result.output


@pytest.mark.parametrize('file_input', [False, True])
def test_malformed_configuration_errors_never_quote_secret_input(api, invoke, tmp_path, file_input):
    malformed = '{"password": "' + SECRET + '" INVALID}'
    if file_input:
        path = tmp_path / 'bad.json'
        path.write_text(malformed)
        args = ['--config-file', str(path)]
    else:
        args = ['--config-json', malformed]
    result = invoke(['apply'] + args + ['--yes'])
    assert result.exit_code != 0
    assert 'Could not read configuration' in result.output
    assert SECRET not in result.output
    assert lifecycle_calls(api) == []


@pytest.mark.parametrize('field,value', [
    ('action', 'delete'), ('tenant_id', ''),
    ('deployment', {}), ('change', None), ('infra', None),
    ('configuration_context_sha256', ''), ('configuration_context_sha256', 'z' * 64),
    ('input_sha256', 'not-a-sha256'), ('input_sha256', None),
    ('infra', {'tag': 'v1.2.3', 'commit': 'short'}),
    ('infra', {'tag': '', 'commit': COMMIT}),
])
def test_incomplete_or_mismatched_preview_never_executes(api, invoke, field, value):
    api.preview = safe_preview('apply')
    api.preview[field] = value
    result = invoke(['apply', '--config-json', json.dumps(STATE), '--tag', 'v1.2.3', '--yes'])
    assert result.exit_code != 0
    assert 'nothing was executed' in result.output
    assert SECRET not in result.output
    assert_no_execute(api)
    assert [c['target'] for c in lifecycle_calls(api)] == [PREFIX + 'preview']


@pytest.mark.parametrize('deployment', [
    {'desired_id': 'different-deployment', 'suffix_policy': 'random suffix'},
    {'desired_id': 'engagement-rt'},
])
def test_launch_identity_mismatch_never_executes(api, invoke, deployment):
    api.preview = safe_preview('launch')
    api.preview['deployment'] = deployment
    result = invoke(['launch', '--desired-id', 'engagement-rt', '--yes'])
    assert result.exit_code != 0
    assert 'nothing was executed' in result.output
    assert_no_execute(api)


@pytest.mark.parametrize('command', ['apply', 'tag'])
def test_preview_for_another_requested_version_is_not_approval(api, invoke, command):
    api.preview = safe_preview('apply' if command == 'apply' else 'update_infrastructure_tag')
    api.preview['infra'] = {'tag': 'v9.9.9', 'commit': 'b' * 40}
    args = [command, '--tag', 'v1.2.3', '--yes']
    if command == 'apply':
        args += ['--config-json', json.dumps(STATE)]
    result = invoke(args)
    assert result.exit_code != 0, 'A preview for another requested version must not execute: ' + result.output
    assert_no_execute(api)


def test_launch_without_pinned_revision_never_executes(api, invoke):
    api.preview = safe_preview('launch')
    api.preview['infra'] = {'tag': '', 'commit': ''}
    result = invoke(['launch', '--desired-id', 'engagement-rt', '--yes'])
    assert result.exit_code != 0, 'Launch approval requires the pinned revision (shared plan decision 12)'
    assert_no_execute(api)


def test_stale_context_conflict_does_not_retry_or_refresh_approval(api, invoke):
    api.errors[PREFIX + 'execute'] = (409, {'message': 'deployment context changed; request a fresh preview'})
    result = invoke(['delete', '--yes'])
    assert result.exit_code != 0
    assert '[409]' in result.output
    assert_preview_rendered(result.output)
    assert [(c['method'], c['target']) for c in lifecycle_calls(api)] == [
        ('POST', PREFIX + 'preview'), ('POST', PREFIX + 'execute'),
    ]


def test_each_approved_invocation_uses_a_new_preview_not_cached_context(api, invoke):
    first = invoke(['delete', '--yes'])
    api.preview = safe_preview()
    api.preview['configuration_context_sha256'] = 'e' * 64
    second = invoke(['delete', '--yes'])
    assert first.exit_code == second.exit_code == 0, first.output + second.output
    calls = lifecycle_calls(api)
    assert [c['target'] for c in calls] == [
        PREFIX + 'preview', PREFIX + 'execute', PREFIX + 'preview', PREFIX + 'execute',
    ]
    assert calls[1]['body']['configuration_context_sha256'] == CONTEXT
    assert calls[3]['body']['configuration_context_sha256'] == 'e' * 64
    assert 'e' * 64 in second.output
