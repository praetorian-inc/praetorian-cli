from datetime import datetime, timezone, timedelta


def _strip_hunt_prefix(uuid):
    """Strip #hunt# prefix if present, returning the bare UUID."""
    return uuid.replace('#hunt#', '') if uuid.startswith('#hunt#') else uuid


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

    def create(self, prompt, expires_hours=72, agent='hannibal', scope=None,
               scope_level='normal', aggressiveness='balanced',
               finish_criteria='', user_guardrails='', allowed_tools=None,
               endpoint_required=False, endpoint_id=None,
               endpoint_confirmed=False):
        """Create and launch a new hunt.

        :param prompt: The hunt objective
        :param expires_hours: Hours until expiry (1-72)
        :param agent: hannibal, hannibal-cloud, hannibal-webapp, hannibal-llm
        :param scope: Optional list of target asset keys
        :param scope_level: normal or strict
        :param aggressiveness: cautious, balanced, or aggressive
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
            for session in status['sessions']:
                sessions[session.get('sessionId')] = session
            for task in status['tasks']:
                tasks[(task.get('endpointId'), task.get('taskId'))] = task
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

    def _update_status(self, uuid, status):
        from praetorian_cli.sdk.chariot import process_failure
        bare = _strip_hunt_prefix(uuid)
        resp = self.api.chariot_request('PUT', self.api.url(f'/hunt/{bare}'), json={'status': status})
        process_failure(resp)
        return resp.json()
