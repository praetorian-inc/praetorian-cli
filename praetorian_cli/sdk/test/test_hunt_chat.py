import pytest

from praetorian_cli.ui.hunt_chat import (
    build_hunt_chat,
    build_hunt_interactions,
    review_pending_hunt_interactions,
    select_hunt_conversation,
)


def _conversation(uuid, status='idle', created='2026-01-01T00:00:00Z', parent='self'):
    return {
        'uuid': uuid,
        'status': status,
        'created': created,
        'parent_id': parent,
        'topic': f'Conversation {uuid}',
    }


def test_select_hunt_conversation_prefers_active_root_iteration():
    conversations = [
        _conversation('idle-new', created='2026-01-01T03:00:00Z'),
        _conversation('active', status='active', created='2026-01-01T02:00:00Z'),
        _conversation('child', status='active', parent='active'),
    ]

    selected = select_hunt_conversation(conversations, require_active=True)

    assert selected['uuid'] == 'active'


def test_select_hunt_conversation_accepts_unique_id_prefix():
    conversations = [
        _conversation('11111111-aaaa', status='active'),
        _conversation('22222222-bbbb'),
    ]

    selected = select_hunt_conversation(
        conversations,
        requested_id='22222222',
    )

    assert selected['uuid'] == '22222222-bbbb'


def test_select_hunt_conversation_rejects_nonmember_and_subagent_guidance():
    conversations = [
        _conversation('root', status='active'),
        _conversation('child', status='active', parent='root'),
    ]

    with pytest.raises(ValueError, match='does not belong'):
        select_hunt_conversation(conversations, requested_id='missing')

    ambiguous = [
        _conversation('same-prefix-one'),
        _conversation('same-prefix-two'),
    ]
    with pytest.raises(ValueError, match='ambiguous'):
        select_hunt_conversation(ambiguous, requested_id='same-prefix')

    with pytest.raises(ValueError, match='root Hunt iteration'):
        select_hunt_conversation(
            conversations,
            requested_id='child',
            require_active=True,
        )


def test_hunt_chat_dashboard_renders_conversations_transcript_and_tools():
    conversations = [
        _conversation('root', status='active'),
        _conversation('child', parent='root'),
    ]
    transcript = {
        'messages': [
            {'role': 'user', 'content': 'Focus on SMB', 'timestamp': '2026-01-01T00:01:00Z'},
            {
                'role': 'tool call',
                'content': 'Running a tool',
                'timestamp': '2026-01-01T00:02:00Z',
                'tool': {
                    'name': 'portscan',
                    'input': {'target': '10.0.0.5'},
                    'response': {'status': 'done'},
                },
            },
            {'role': 'chariot', 'content': 'Continuing with SMB.', 'timestamp': '2026-01-01T00:03:00Z'},
        ],
    }

    # Reuse Rich's plain rendering helper to make the Group assertion-friendly.
    from io import StringIO
    from rich.console import Console

    output = StringIO()
    Console(file=output, width=100, color_system=None).print(
        build_hunt_chat(conversations, conversations[0], transcript)
    )
    rendered = output.getvalue()

    assert 'Hannibal Hunt Chat' in rendered
    assert 'Iteration root' in rendered
    assert '↳ Conversation child' in rendered
    assert rendered.index('Iteration root') < rendered.index('↳ Conversation child')
    assert 'Focus on SMB' in rendered
    assert 'portscan' in rendered
    assert 'Target: 10.0.0.5' in rendered
    assert 'Continuing with SMB.' in rendered


def test_hunt_interactions_render_safe_metadata_in_chat_without_request_text():
    from io import StringIO
    from rich.console import Console

    pending = [{
        'conversationId': 'child-conversation',
        'requestId': 'request-1',
        'kind': 'credential',
        'status': 'pending',
        'request': 'MODEL TEXT WITH VALUE-THAT-MUST-NOT-RENDER',
        'fields': ['username', 'password'],
    }]
    conversations = [_conversation('root', status='active')]
    output = StringIO()
    console = Console(file=output, width=120, color_system=None)

    console.print(build_hunt_interactions(pending))
    console.print(build_hunt_chat(
        conversations,
        conversations[0],
        {'messages': []},
        pending_interactions=pending,
    ))
    rendered = output.getvalue()

    assert 'Pending Hunt interactions' in rendered
    assert 'Pending operator interactions' in rendered
    assert 'child-conver' in rendered
    assert 'username, password' in rendered
    assert 'VALUE-THAT-MUST-NOT-RENDER' not in rendered


def test_hunt_interaction_reviewer_reuses_secure_kind_specific_primitives(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        'praetorian_cli.ui.hunt_chat.prompt_endpoint_approval',
        lambda sdk, interaction, **kwargs: calls.append((
            'approval', interaction['requestId'], kwargs['interactive'],
        )),
    )
    monkeypatch.setattr(
        'praetorian_cli.ui.hunt_chat.prompt_ephemeral_credentials',
        lambda sdk, interaction, **kwargs: calls.append((
            'credential', interaction['requestId'], kwargs['interactive'],
        )),
    )

    class Console:
        def print(self, *_args, **_kwargs):
            pass

    interactions = [
        {'kind': 'approval', 'requestId': 'approval-1'},
        {'kind': 'credential', 'requestId': 'credential-1'},
        {'kind': 'future-kind', 'requestId': 'future-1'},
    ]
    handled = set()
    review_pending_hunt_interactions(
        object(),
        interactions,
        Console(),
        confirm=lambda *_args, **_kwargs: False,
        credential_prompt=lambda _field: 'VALUE',
        handled=handled,
        interactive=True,
    )
    review_pending_hunt_interactions(
        object(),
        interactions,
        Console(),
        confirm=lambda *_args, **_kwargs: False,
        credential_prompt=lambda _field: 'VALUE',
        handled=handled,
        interactive=True,
    )

    assert calls == [
        ('approval', 'approval-1', True),
        ('credential', 'credential-1', True),
    ]
