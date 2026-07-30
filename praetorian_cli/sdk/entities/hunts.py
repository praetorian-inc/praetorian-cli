from datetime import datetime, timezone, timedelta


class Hunts:
    """Hunt management methods, accessed via sdk.hunts."""

    def __init__(self, api):
        self.api = api

    def create(self, prompt, expires_hours=72, agent='hannibal', scope=None,
               scope_level='normal', aggressiveness='balanced',
               finish_criteria='', user_guardrails='', allowed_tools=None):
        """Create and launch a new hunt.

        :param prompt: The hunt objective
        :param expires_hours: Hours until expiry (max 72)
        :param agent: hannibal, hannibal-cloud, hannibal-webapp, hannibal-llm
        :param scope: Optional list of target asset keys
        :param scope_level: normal or strict
        :param aggressiveness: cautious, balanced, or aggressive
        :return: The created hunt object
        """
        hours = min(expires_hours, 72)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')

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

        return self.api.post('hunt', body)

    def list(self, status=None, pages=1):
        """List hunts for the current account via graph search.

        :param status: Optional status filter (active, paused, completed, stopped, expired, errored)
        :param pages: Number of pages to fetch
        :return: Tuple of (list of hunts, offset)
        """
        result = self.api.my({'key': '#hunt#'}, pages=pages)
        data = result.get('data', [])
        if status:
            data = [h for h in data if h.get('status') == status]
        return data, result.get('offset')

    def get(self, uuid):
        """Get a single hunt by UUID.

        :param uuid: Hunt UUID (with or without #hunt# prefix)
        :return: Hunt dict or None
        """
        key = f'#hunt#{uuid}' if not uuid.startswith('#hunt#') else uuid
        result = self.api.my({'key': key})
        data = result.get('data', [])
        return data[0] if data else None

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
        resp = self.api.chariot_request('DELETE', self.api.url(f'/hunt/{uuid}'))
        process_failure(resp)
        return resp.json()

    def _update_status(self, uuid, status):
        from praetorian_cli.sdk.chariot import process_failure
        resp = self.api.chariot_request('PUT', self.api.url(f'/hunt/{uuid}'), json={'status': status})
        process_failure(resp)
        return resp.json()
