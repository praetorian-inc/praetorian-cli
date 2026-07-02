import json

from praetorian_cli.sdk.entities.search import flatten_results


class Conversations:
    """Read Guard AI conversations and their full message/tool-call history.

    Accessed as sdk.conversations."""

    def __init__(self, api):
        self.api = api

    def list(self, scope='user', offset=None, pages=100000) -> tuple:
        """List conversations, most recent first.

        :param scope: which partition to read:
            'user' (default) your private conversations;
            'tenant' tenant-shared conversations (public + hunt-owned);
            'all' the union of both, de-duplicated.
        :return: (list of conversation dicts, next page offset)
        :rtype: tuple
        """
        if scope == 'user':
            convos, offset = self.api.search.by_key_prefix('#conversation#', offset=offset, pages=pages, user=True)
        elif scope == 'tenant':
            convos, offset = self._shared(offset, pages)
        elif scope == 'all':
            mine, _ = self.api.search.by_key_prefix('#conversation#', pages=pages, user=True)
            shared, _ = self._shared(None, pages)
            seen = {c.get('uuid') for c in mine}
            convos, offset = mine + [c for c in shared if c.get('uuid') not in seen], None
        else:
            raise ValueError(f"scope must be 'user', 'tenant', or 'all', got: {scope!r}")
        convos.sort(key=lambda c: c.get('created') or '', reverse=True)
        return convos, offset

    def get(self, conversation_id) -> dict:
        """Get a full conversation transcript, including every tool call.

        Routes via ``convId`` so it resolves the correct partition whether the
        conversation is user-scoped, public, or hunt-owned.

        :param conversation_id: the conversation uuid
        :return: {uuid, topic, created, status, messages}, where each message is
            {role, content, timestamp}; tool-call messages also carry a parsed
            ``tool`` of {name, input, response, tool_use_id}.
        :rtype: dict
        """
        meta = self._routed(f'#conversation#{conversation_id}', conversation_id)
        records = self._routed(f'#message#{conversation_id}#', conversation_id)
        if not meta and not records:
            raise ValueError(f'No conversation found for id: {conversation_id}')
        return _transcript(conversation_id, meta[0] if meta else {}, records)

    def _shared(self, offset, pages) -> tuple:
        # The tenant partition (no user flag) mixes shared conversations in with
        # other tenant records; keep only the public and hunt-owned ones.
        convos, offset = self.api.search.by_key_prefix('#conversation#', offset=offset, pages=pages)
        return [c for c in convos if c.get('public') or c.get('hunt')], offset

    def _routed(self, key, conversation_id) -> list:
        results = self.api.my({'key': key, 'convId': conversation_id}, pages=100000)
        results.pop('offset', None)
        return flatten_results(results)


def _transcript(uuid, meta, records) -> dict:
    # messageId is a UUIDv7, so sorting by key orders messages chronologically.
    records = sorted(records, key=lambda r: r.get('key', ''))
    responses = {r.get('toolUseId'): r for r in records if r.get('role') == 'tool response'}

    messages = []
    for r in records:
        role = r.get('role', '')
        if role == 'tool response':
            continue  # folded into its originating 'tool call'
        message = dict(role=role, content=r.get('content', ''), timestamp=r.get('timestamp', ''))
        if role == 'tool call':
            message['tool'] = _tool_call(r, responses)
        messages.append(message)

    return dict(uuid=uuid, topic=meta.get('topic') or '', created=meta.get('created') or '',
                status=meta.get('status') or '', messages=messages)


def _tool_call(call, responses) -> dict:
    spec = _loads(call.get('toolUseContent'))
    if not isinstance(spec, dict):
        spec = {}
    tool_use_id = spec.get('ToolUseID') or call.get('toolUseId', '')
    response = responses.get(tool_use_id)
    return dict(name=spec.get('Name', ''), input=spec.get('Input'),
                response=_loads(response.get('content')) if response else None,
                tool_use_id=tool_use_id)


def _loads(raw):
    """Parse a JSON string into an object; pass through anything else unchanged."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw
