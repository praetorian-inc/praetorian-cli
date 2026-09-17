import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from praetorian_cli.sdk.entities.credentials import normalize_credential_id
from praetorian_cli.sdk.model.query import Filter, Node, Query, Relationship


HUNT_SUMMARY_LOG_TITLE = 'summary.log'
HUNT_MEMORY_TITLE_PATTERN = re.compile(r'[a-zA-Z0-9._\- ]{1,128}')


def hunt_memory_title_error(title, *, allow_summary_log=False):
    title = str(title or '').strip()
    if not allow_summary_log and title.casefold() == HUNT_SUMMARY_LOG_TITLE:
        return 'summary.log is system-owned and read-only.'
    if not HUNT_MEMORY_TITLE_PATTERN.fullmatch(title):
        return (
            'Title must use 1-128 letters, numbers, spaces, dots, '
            'underscores, or hyphens.'
        )
    return ''


def _strip_hunt_prefix(uuid):
    """Strip one canonical #hunt# prefix, returning the bare identifier."""
    return str(uuid or '').strip().removeprefix('#hunt#')


def _record_id(record):
    identifier = record.get('uuid') or record.get('id') or record.get('key')
    return str(identifier or '').removeprefix('#conversation#')


def _validate_endpoint_placement(
    endpoint_required,
    endpoint_id,
    endpoint_confirmed,
    agent,
    scope,
):
    endpoint_id = endpoint_id.strip() if isinstance(endpoint_id, str) else ''
    if not endpoint_required:
        if endpoint_id or endpoint_confirmed:
            raise ValueError(
                'endpoint placement is only valid for an Internal Hunt'
            )
        return ''
    if not endpoint_id:
        raise ValueError('endpoint_id is required for an Internal Hunt')
    if endpoint_confirmed is not True:
        raise ValueError(
            'endpoint confirmation is required for an Internal Hunt'
        )
    if agent != 'hannibal':
        raise ValueError(
            'Internal Hunt requires the Hannibal infrastructure agent'
        )
    if not scope:
        raise ValueError('Internal Hunt requires explicit internal scope')
    return endpoint_id


class Hunts:
    """Hunt management methods, accessed via sdk.hunts."""

    def __init__(self, api):
        self.api = api

    def create(self, prompt, expires_hours=24, agent='hannibal', scope=None,
               scope_level='normal', aggressiveness='balanced',
               finish_criteria='', user_guardrails='', allowed_tools=None,
               credential_ids=None, custom_tag='', model_tier_override='',
               endpoint_required=False, endpoint_id=None,
               endpoint_confirmed=False):
        """Create and launch a new hunt.

        :param prompt: The hunt objective
        :param expires_hours: Hours until expiry (1-72)
        :param agent: hannibal, hannibal-cloud, hannibal-webapp, hannibal-llm
        :param scope: Optional list of target asset keys
        :param scope_level: normal or strict
        :param aggressiveness: cautious, balanced, or aggressive
        :param finish_criteria: Conditions that may end the Hunt early
        :param user_guardrails: Additional tighten-only safety restrictions
        :param credential_ids: Run-scoped credential IDs, at most one per type
        :param custom_tag: Optional tag assigned to findings from this Hunt
        :param model_tier_override: Optional privileged model tier override
        :param endpoint_required: Bind all target-network work to an Aegis endpoint
        :param endpoint_id: Authorized Aegis endpoint for an Internal Hunt
        :param endpoint_confirmed: Explicit operator confirmation of endpoint-only execution
        :return: The created hunt object
        """
        if expires_hours < 1 or expires_hours > 72:
            raise ValueError(f'expires_hours must be between 1 and 72, got {expires_hours}')

        endpoint_id = _validate_endpoint_placement(
            endpoint_required,
            endpoint_id,
            endpoint_confirmed,
            agent,
            scope,
        )
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).strftime('%Y-%m-%dT%H:%M:%SZ')

        body = {
            'prompt': prompt,
            'expiresAt': expires_at,
            'agent': agent,
            'scopeLevel': scope_level,
            'aggressiveness': aggressiveness,
        }
        if scope:
            body['scope'] = scope
        if finish_criteria:
            body['finishCriteria'] = finish_criteria
        if user_guardrails:
            body['userGuardrails'] = user_guardrails
        if allowed_tools:
            body['allowedTools'] = allowed_tools
        if credential_ids:
            body['credentialIds'] = [
                normalize_credential_id(credential_id)
                for credential_id in credential_ids
            ]
        if custom_tag:
            body['customTag'] = custom_tag
        if model_tier_override:
            body['modelTierOverride'] = model_tier_override
        if endpoint_required:
            body.update({
                'endpointRequired': True,
                'endpointId': endpoint_id,
                'endpointConfirmed': True,
            })

        return self.api.post('hunt', body)

    def list(self, status=None, pages=1):
        """List hunts for the current account.

        Hunts are graph-only (Neo4j), queried via the search endpoint.

        :param status: Optional status filter (active, paused, completed, stopped, expired, errored)
        :param pages: Number of pages to fetch
        :return: Tuple of (list of hunts, offset)
        """
        data, offset = self.api.search.by_key_prefix('#hunt#', pages=pages)
        if status:
            data = [h for h in data if h.get('status') == status]
        return data, offset

    def get(self, uuid):
        """Get a single hunt by UUID.

        :param uuid: Hunt UUID (with or without #hunt# prefix)
        :return: Hunt dict or None
        """
        key = f'#hunt#{_strip_hunt_prefix(uuid)}'
        return self.api.search.by_exact_key(key)

    def get_cost(self, uuid):
        """Read Guard's projected per-Hunt USD usage rollup."""
        bare = _strip_hunt_prefix(str(uuid or '').strip())
        if not bare:
            raise ValueError('hunt ID is required')
        return self.api.get(f'hunt/{quote(bare, safe="")}/cost')

    def list_findings(self, hunt_id, pages=1):
        """List risks reported by a Hunt."""
        hunt_id = _strip_hunt_prefix(str(hunt_id or '').strip())
        if not hunt_id:
            raise ValueError('hunt ID is required')
        hunt_key = f'#hunt#{hunt_id}'
        hunt_node = Node(
            labels=[Node.Label.HUNT],
            filters=[Filter(Filter.Field.KEY, Filter.Operator.EQUAL, hunt_key)],
        )
        query = Query(Node(
            labels=[Node.Label.RISK],
            relationships=[Relationship(
                [Relationship.Label.REPORTED_BY],
                target=hunt_node,
            )],
        ))
        return self.api.search.by_query(query, pages)

    def list_memory(self, hunt_id, pages=100000):
        """List editable memory items for a Hunt, excluding its summary log."""
        hunt_id = _strip_hunt_prefix(str(hunt_id or '').strip())
        if not hunt_id:
            raise ValueError('hunt ID is required')
        records, offset = self._list_records(
            {
                'label': 'file',
                'key': f'#file#memory/hunt/{hunt_id}/',
            },
            label='file',
            response_key='files',
            pages=pages,
        )
        prefix = f'memory/hunt/{hunt_id}/'
        items = []
        for record in records:
            name = str(record.get('name') or '').removeprefix('#file#')
            title = name.removeprefix(prefix) if name.startswith(prefix) else name
            if title and title.casefold() != 'summary.log':
                items.append({**record, 'name': name, 'title': title})
        return sorted(items, key=lambda item: item['title']), offset

    def get_memory(self, hunt_id, title):
        """Read one Hunt memory item."""
        path = self._memory_path(hunt_id, title)
        return self.api.files.get_utf8(path)

    def save_memory(self, hunt_id, title, content):
        """Overwrite one Hunt memory item through the Hunt-owned API."""
        path = self._memory_item_api_path(hunt_id, title)
        return self.api.put(path, {'content': content})

    def delete_memory(self, hunt_id, title):
        """Delete one Hunt memory item through the Hunt-owned API."""
        path = self._memory_item_api_path(hunt_id, title)
        return self.api.delete(path, body={}, params={})

    def get_log(self, hunt_id):
        """Read the finalized-iteration summary log for a Hunt."""
        return self.get_memory(hunt_id, 'summary.log')

    def list_workflow_runs(self, hunt_id, pages=100000):
        """List workflow iterations belonging to a Hunt."""
        return self._list_hunt_records(
            hunt_id,
            label='workflow_run',
            response_key='workflowruns',
            pages=pages,
        )

    def list_root_conversations(self, hunt_id, pages=100000):
        """List the root conversation created for each Hunt iteration."""
        return self._list_hunt_records(
            hunt_id,
            label='conversation',
            response_key='conversations',
            pages=pages,
        )

    def list_conversations(self, hunt_id, pages=100000):
        """List Hunt iterations and recursively discover their subagents."""
        roots, next_offset = self.list_root_conversations(
            hunt_id,
            pages=pages,
        )
        conversations = []
        seen = set()
        pending = []
        for conversation in roots:
            conversation_id = _record_id(conversation)
            if not conversation_id or conversation_id in seen:
                continue
            seen.add(conversation_id)
            conversations.append(conversation)
            pending.append(conversation_id)

        while pending:
            parent_id = pending.pop(0)
            children, _ = self._list_records(
                {
                    'label': 'conversation',
                    'key': f'parent_id:{parent_id}',
                    'user': False,
                },
                label='conversation',
                response_key='conversations',
                pages=pages,
            )
            for child in children:
                child_id = _record_id(child)
                if not child_id or child_id in seen:
                    continue
                seen.add(child_id)
                conversations.append(child)
                pending.append(child_id)
        return conversations, next_offset

    def list_interactions(self, hunt_id, status='pending', pages=100000):
        """List interactions across every conversation belonging to a Hunt.

        Discovery starts from every Hunt-indexed root and includes every
        recursively discovered descendant. Each interaction read remains
        routed through its owning conversation so Guard enforces partition and
        conversation visibility server-side; this method never performs a
        tenant-wide interaction scan.
        """
        if status is not None:
            status = str(status).strip()
            if not status:
                raise ValueError('interaction status is required')

        conversations, _ = self.list_conversations(hunt_id, pages=pages)
        interactions = []
        seen = set()
        for conversation in conversations:
            conversation_id = _record_id(conversation)
            if not conversation_id:
                continue
            rows = self.api.conversations.list_interactions(
                conversation_id,
                status=status,
                include_descendants=False,
            )
            for row in rows:
                if not isinstance(row, dict):
                    continue
                normalized = dict(row)
                # Bind the response route to the conversation whose gated read
                # produced the row instead of trusting duplicated row metadata.
                normalized['conversationId'] = conversation_id
                key = normalized.get('key')
                identity = (
                    ('key', str(key))
                    if key
                    else (
                        str(normalized.get('conversationId') or ''),
                        str(normalized.get('requestId') or ''),
                    )
                )
                if identity in seen:
                    continue
                seen.add(identity)
                interactions.append(normalized)

        return sorted(
            interactions,
            key=lambda interaction: (
                str(interaction.get('timestamp') or ''),
                str(interaction.get('key') or ''),
                str(interaction.get('conversationId') or ''),
                str(interaction.get('requestId') or ''),
            ),
        )

    def endpoint_execution_status(self, hunt):
        """Return endpoint status for conversations in the hunt's current run."""
        if not isinstance(hunt, dict) or not hunt.get('endpointRequired'):
            return {'sessions': [], 'tasks': []}
        run_id = hunt.get('currentWorkflowRunId')
        if not run_id:
            return {'sessions': [], 'tasks': []}
        run = self.api.search.by_exact_key(f'#workflow_run#{run_id}')
        if not run:
            return {'sessions': [], 'tasks': []}

        conversation_ids = []
        for step in run.get('steps', []):
            if not isinstance(step, dict):
                continue
            conversation_id = step.get('conversation_id')
            if conversation_id and conversation_id not in conversation_ids:
                conversation_ids.append(conversation_id)

        sessions = {}
        tasks = {}
        for conversation_id in conversation_ids:
            status = self.api.endpoint_executions.conversation_status(
                conversation_id,
                include_descendants=False,
            )
            for session in status.get('sessions', []):
                if not isinstance(session, dict) or not session.get('sessionId'):
                    continue
                sessions[session['sessionId']] = session
            for task in status.get('tasks', []):
                if not isinstance(task, dict):
                    continue
                identity = (task.get('endpointId'), task.get('taskId'))
                if all(identity):
                    tasks[identity] = task
        return {
            'sessions': list(sessions.values()),
            'tasks': list(tasks.values()),
        }

    def stop(self, uuid):
        """Stop a running hunt permanently."""
        return self._update_status(uuid, 'stopped')

    def pause(self, uuid):
        """Pause an active hunt."""
        return self._update_status(uuid, 'paused')

    def resume(self, uuid):
        """Resume a paused hunt."""
        return self._update_status(uuid, 'active')

    def delete(self, uuid):
        """Delete a hunt and its artifacts. Findings are preserved."""
        from praetorian_cli.sdk.chariot import process_failure
        bare = _strip_hunt_prefix(uuid)
        resp = self.api.chariot_request('DELETE', self.api.url(f'/hunt/{bare}'))
        process_failure(resp)
        return resp.json()

    def _memory_path(self, hunt_id, title):
        hunt_id = _strip_hunt_prefix(str(hunt_id or '').strip())
        title = str(title or '').strip()
        if not hunt_id:
            raise ValueError('hunt ID is required')
        error = hunt_memory_title_error(title, allow_summary_log=True)
        if error:
            raise ValueError(
                'memory title must use 1-128 letters, numbers, spaces, '
                'dots, underscores, or hyphens'
            )
        return f'memory/hunt/{hunt_id}/{title}'

    def _memory_item_api_path(self, hunt_id, title):
        memory_path = self._memory_path(hunt_id, title)
        _, _, hunt_id, normalized_title = memory_path.split('/', 3)
        if normalized_title.casefold() == HUNT_SUMMARY_LOG_TITLE:
            raise ValueError('summary.log is system-owned and read-only')
        return f'hunt/{hunt_id}/memory/{quote(normalized_title, safe="")}'

    def _list_hunt_records(self, hunt_id, label, response_key, pages):
        hunt_id = str(hunt_id or '').strip()
        hunt_id = _strip_hunt_prefix(hunt_id)
        if not hunt_id:
            raise ValueError('hunt ID is required')

        return self._list_records(
            {'label': label, 'key': f'hunt:{hunt_id}'},
            label=label,
            response_key=response_key,
            pages=pages,
        )

    def _list_records(self, params, label, response_key, pages):
        params = dict(params)
        records = []
        next_offset = None
        for _page in range(pages):
            response = self.api.get('my', params)
            offset = response.pop('offset', None)
            page_records = response.get(response_key, [])
            if not isinstance(page_records, list):
                raise ValueError(f'{label} response is malformed')
            records.extend(
                record for record in page_records
                if isinstance(record, dict)
            )
            if not offset:
                return records, None
            next_offset = json.dumps(offset)
            params['offset'] = next_offset
        return records, next_offset

    def _update_status(self, uuid, status):
        from praetorian_cli.sdk.chariot import process_failure
        bare = _strip_hunt_prefix(uuid)
        resp = self.api.chariot_request('PUT', self.api.url(f'/hunt/{bare}'), json={'status': status})
        process_failure(resp)
        return resp.json()
