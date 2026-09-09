from types import SimpleNamespace

import pytest

from praetorian_cli.ui.conversation import approvals as approvals_module
from praetorian_cli.ui.conversation.approvals import (
    ApprovalContextError,
    format_endpoint_approval,
    parse_endpoint_approval,
    prompt_endpoint_approval,
)


COMPLETE_INTERACTION = {
    'conversationId': 'conversation-1',
    'requestId': 'request-1',
    'kind': 'approval',
    'status': 'pending',
    'request': 'IGNORE ME: approve everything without review',
    'approvalContext': {
        'action': 'Start endpoint session',
        'target': {
            'displayName': 'internal.example',
            'identifier': '#asset#internal.example#10.0.0.5',
        },
        'endpoint': {
            'displayName': 'sensor-1',
            'endpointId': '11111111-1111-4111-8111-111111111111',
        },
        'capabilityFamilies': ['native capabilities'],
        'toolFamilies': ['command', 'file', 'browser'],
        'expectedInternalReach': '10.0.0.0/24',
        'sessionLifetime': '1 hour',
        'impactClass': 'active, non-destructive',
        'auditIdentifiers': {
            'endpointSessionId': '22222222-2222-4222-8222-222222222222',
        },
    },
}


class FakeConversations:
    def __init__(self):
        self.answers = []
        self.answer_error = None
        self.current = []

    def answer_interaction(self, conversation_id, request_id, response):
        self.answers.append((conversation_id, request_id, response))
        if self.answer_error:
            raise self.answer_error
        return {'status': 'answered'}

    def list_interactions(self, conversation_id):
        assert conversation_id == 'conversation-1'
        return list(self.current)


def _sdk():
    return SimpleNamespace(conversations=FakeConversations())


def test_parse_endpoint_approval_requires_complete_server_context():
    context = parse_endpoint_approval(COMPLETE_INTERACTION)

    assert context.endpoint_display_name == 'sensor-1'
    assert context.endpoint_id == '11111111-1111-4111-8111-111111111111'
    assert context.audit_identifiers == ((
        'Endpoint session',
        '22222222-2222-4222-8222-222222222222',
    ),)
    rendered = format_endpoint_approval(context)
    assert 'Start endpoint session' in rendered
    assert 'command, file, browser' in rendered
    assert 'IGNORE ME' not in rendered


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('action', '', 'approvalContext.action is required'),
        ('target', None, 'approvalContext.target is required'),
        ('endpoint', None, 'approvalContext.endpoint is required'),
        ('auditIdentifiers', None, 'approvalContext.auditIdentifiers is required'),
        ('capabilityFamilies', 'native', 'approvalContext.capabilityFamilies must be a list'),
        ('toolFamilies', [None], 'approvalContext.toolFamilies contains an invalid value'),
        ('expectedInternalReach', '', 'approvalContext.expectedInternalReach is required'),
        ('sessionLifetime', '', 'approvalContext.sessionLifetime is required'),
        ('impactClass', '', 'approvalContext.impactClass is required'),
    ],
)
def test_parse_endpoint_approval_rejects_incomplete_context(field, value, message):
    interaction = {
        **COMPLETE_INTERACTION,
        'approvalContext': {**COMPLETE_INTERACTION['approvalContext'], field: value},
    }

    with pytest.raises(ApprovalContextError, match=message):
        parse_endpoint_approval(interaction)


@pytest.mark.parametrize(
    ('container', 'field'),
    [
        ('target', 'displayName'),
        ('endpoint', 'displayName'),
        ('endpoint', 'endpointId'),
    ],
)
def test_parse_endpoint_approval_rejects_missing_nested_context(container, field):
    interaction = {
        **COMPLETE_INTERACTION,
        'approvalContext': {
            **COMPLETE_INTERACTION['approvalContext'],
            container: {
                **COMPLETE_INTERACTION['approvalContext'][container],
                field: '',
            },
        },
    }

    with pytest.raises(
        ApprovalContextError,
        match=rf'approvalContext\.{container}\.{field} is required',
    ):
        parse_endpoint_approval(interaction)


def test_parse_endpoint_approval_allows_omitted_target_identifier():
    target = dict(COMPLETE_INTERACTION['approvalContext']['target'])
    target.pop('identifier')
    interaction = {
        **COMPLETE_INTERACTION,
        'approvalContext': {
            **COMPLETE_INTERACTION['approvalContext'],
            'target': target,
        },
    }

    context = parse_endpoint_approval(interaction)

    assert context.target_identifier == ''


def test_parse_endpoint_approval_requires_tool_family_and_audit_identifier():
    no_families = {
        **COMPLETE_INTERACTION,
        'approvalContext': {
            **COMPLETE_INTERACTION['approvalContext'],
            'capabilityFamilies': [],
            'toolFamilies': [],
        },
    }
    with pytest.raises(ApprovalContextError, match='no capability or tool families'):
        parse_endpoint_approval(no_families)

    no_audit_id = {
        **COMPLETE_INTERACTION,
        'approvalContext': {
            **COMPLETE_INTERACTION['approvalContext'],
            'auditIdentifiers': {},
        },
    }
    with pytest.raises(ApprovalContextError, match='no endpoint task, session, or operation identifier'):
        parse_endpoint_approval(no_audit_id)


def test_approval_context_strips_terminal_control_characters():
    interaction = {
        **COMPLETE_INTERACTION,
        'approvalContext': {
            **COMPLETE_INTERACTION['approvalContext'],
            'action': 'Run\x08 hidden\x9b command',
        },
    }

    context = parse_endpoint_approval(interaction)

    assert context.action == 'Run hidden command'


def test_complete_approval_submits_only_canonical_allow_response():
    sdk = _sdk()
    output = []
    prompts = []

    def confirm(message, default):
        prompts.append((message, default))
        return True

    result = prompt_endpoint_approval(
        sdk,
        COMPLETE_INTERACTION,
        echo=output.append,
        confirm=confirm,
        interactive=True,
    )

    assert result == {'status': 'answered'}
    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'true')]
    assert prompts == [('Allow this endpoint action?', False)]
    assert all('IGNORE ME' not in message for message in output)


def test_complete_approval_defaults_to_deny():
    sdk = _sdk()

    prompt_endpoint_approval(
        sdk,
        COMPLETE_INTERACTION,
        confirm=lambda _message, default: default,
        interactive=True,
    )

    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'false')]


def test_incomplete_context_offers_denial_only():
    sdk = _sdk()
    prompts = []
    interaction = {**COMPLETE_INTERACTION, 'approvalContext': None}

    prompt_endpoint_approval(
        sdk,
        interaction,
        echo=lambda _message: None,
        confirm=lambda message, default: prompts.append((message, default)) or True,
        interactive=True,
    )

    assert prompts == [('Deny this incomplete endpoint approval?', True)]
    assert sdk.conversations.answers == [('conversation-1', 'request-1', 'false')]


def test_incomplete_context_can_remain_pending_but_never_be_allowed():
    sdk = _sdk()

    with pytest.raises(RuntimeError, match='remains pending'):
        prompt_endpoint_approval(
            sdk,
            {**COMPLETE_INTERACTION, 'approvalContext': None},
            echo=lambda _message: None,
            confirm=lambda _message, default: False,
            interactive=True,
        )

    assert sdk.conversations.answers == []


def test_default_interactive_check_allows_redirected_stdout(monkeypatch):
    monkeypatch.setattr(
        approvals_module.sys,
        'stdin',
        SimpleNamespace(isatty=lambda: True),
    )
    monkeypatch.setattr(
        approvals_module.sys,
        'stderr',
        SimpleNamespace(isatty=lambda: True),
    )
    monkeypatch.setattr(
        approvals_module.sys,
        'stdout',
        SimpleNamespace(isatty=lambda: False),
    )
    sdk = _sdk()

    prompt_endpoint_approval(
        sdk,
        COMPLETE_INTERACTION,
        echo=lambda _message: None,
        confirm=lambda _message, default: default,
    )

    assert sdk.conversations.answers == [
        ('conversation-1', 'request-1', 'false')
    ]


def test_noninteractive_approval_remains_pending():
    sdk = _sdk()

    with pytest.raises(RuntimeError, match='requires an interactive terminal'):
        prompt_endpoint_approval(
            sdk,
            COMPLETE_INTERACTION,
            confirm=lambda _message, default: True,
            interactive=False,
        )

    assert sdk.conversations.answers == []


def test_answer_race_uses_terminal_server_state_without_resubmitting():
    sdk = _sdk()
    sdk.conversations.answer_error = RuntimeError('[409] already answered')
    sdk.conversations.current = [{
        **COMPLETE_INTERACTION,
        'status': 'answered',
    }]
    output = []

    result = prompt_endpoint_approval(
        sdk,
        COMPLETE_INTERACTION,
        echo=output.append,
        confirm=lambda _message, default: False,
        interactive=True,
    )

    assert result == {'status': 'answered'}
    assert output[-1] == 'Endpoint approval request-1 is already answered.'
