import json
from time import monotonic

from praetorian_cli.sdk.entities.search import flatten_results


TREE_CACHE_TTL_SECONDS = 10


class Conversations:
    """Read Guard AI conversations and their full message/tool-call history.

    Accessed as sdk.conversations."""

    def __init__(self, api):
        self.api = api
        self._tree_cache = {}

    def list(self, scope='user', offset=None, pages=100000) -> tuple:
        """List conversations, most recent first.

        :param scope: which partition to read:
            'user' (default) your private conversations;
            'tenant' tenant-shared conversations (public + hunt-owned);
            'all' the union of both, de-duplicated (fetched in full; not paginated).
        :return: (list of conversation dicts, next page offset)
        :rtype: tuple
        """
        if scope == 'user':
            convos, offset = self.api.search.by_key_prefix('#conversation#', offset=offset, pages=pages, user=True)
        elif scope == 'tenant':
            convos, offset = self._shared(offset, pages)
        elif scope == 'all':
            # A newest-first union of two partitions can't be resumed by a single
            # cursor, so drain both fully (by_key_prefix pages through with extend)
            # and merge. 'all' is intentionally unpaginated; `pages` is ignored.
            mine, _ = self.api.search.by_key_prefix('#conversation#', user=True)
            shared, _ = self._shared()
            convos, offset = mine + shared, None
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

    def list_interactions(
        self,
        conversation_id,
        status=None,
        include_descendants=False,
    ) -> list:
        """List durable interactions for a conversation or conversation tree.

        The ``convId`` parameter lets Guard resolve private and hunt/public
        conversation partitions server-side. Unknown interaction kinds are
        returned unchanged.
        """
        conversation_id = _required_string(conversation_id, 'conversation ID')
        if status is not None:
            status = _required_string(status, 'interaction status')

        conversation_ids = (
            self.tree_ids(conversation_id)
            if include_descendants
            else [conversation_id]
        )

        interactions = []
        for current_id in conversation_ids:
            interactions.extend(self._routed(
                f'#interaction#{current_id}#', current_id
            ))
        if status is not None:
            interactions = [
                interaction for interaction in interactions
                if interaction.get('status') == status
            ]
        return sorted(
            interactions,
            key=lambda interaction: (
                interaction.get('timestamp', ''),
                interaction.get('key', ''),
            ),
        )

    def tree_ids(self, conversation_id) -> list:
        """Return a cached, bounded conversation tree."""
        conversation_id = _required_string(conversation_id, 'conversation ID')
        now = monotonic()
        cached = self._tree_cache.get(conversation_id)
        if cached and cached[0] > now:
            return list(cached[1])

        conversation_ids = [
            conversation_id,
            *self._descendant_ids(conversation_id),
        ]
        self._tree_cache[conversation_id] = (
            now + TREE_CACHE_TTL_SECONDS,
            tuple(conversation_ids),
        )
        return conversation_ids

    def stop(self, conversation_id) -> dict:
        """Stop a conversation and its Guard-correlated child work."""
        conversation_id = _required_string(conversation_id, 'conversation ID')
        return self.api.post('planner/stop', {
            'conversationId': conversation_id,
        })

    def answer_interaction(self, conversation_id, request_id, response) -> dict:
        """Answer one durable conversation interaction."""
        conversation_id = _required_string(conversation_id, 'conversation ID')
        request_id = _required_string(request_id, 'request ID')
        response = _required_string(response, 'interaction response', strip=False)
        return self.api.post('planner/interaction', {
            'conversationId': conversation_id,
            'requestId': request_id,
            'response': response,
        })

    def _descendant_ids(self, root_id, max_depth=5, max_ids=200):
        descendants = []
        seen = {root_id}
        frontier = [root_id]
        for _depth in range(max_depth):
            next_frontier = []
            for parent_id in frontier:
                for user_partition in (True, False):
                    children = self._children(parent_id, user_partition)
                    for child in children:
                        child_id = child.get('uuid') or child.get('id')
                        if not child_id or child_id in seen:
                            continue
                        seen.add(child_id)
                        descendants.append(child_id)
                        next_frontier.append(child_id)
                        if len(descendants) >= max_ids:
                            return descendants
            if not next_frontier:
                break
            frontier = next_frontier
        return descendants

    def _children(self, parent_id, user_partition, pages=100000):
        params = {
            'key': f'parent_id:{parent_id}',
            'label': 'conversation',
        }
        if user_partition:
            params['user'] = 'true'

        children = []
        for _page in range(pages):
            results = self.api.get('my', params)
            offset = results.pop('offset', None)
            children.extend(flatten_results(results))
            if not offset:
                return children
            params['offset'] = json.dumps(offset)

        raise RuntimeError(
            'conversation child listing exceeded its page limit; '
            f'remaining offset: {params.get("offset")}'
        )

    def _shared(self, offset=None, pages=100000) -> tuple:
        # The tenant partition (no user flag) mixes shared conversations in with
        # other tenant records; keep only the public and hunt-owned ones.
        convos, offset = self.api.search.by_key_prefix('#conversation#', offset=offset, pages=pages)
        return [c for c in convos if c.get('public') or c.get('hunt')], offset

    def _routed(self, key, conversation_id) -> list:
        results = self.api.my({'key': key, 'convId': conversation_id}, pages=100000)
        results.pop('offset', None)
        return flatten_results(results)


def _required_string(value, name, strip=True):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} is required')
    return value.strip() if strip else value


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
