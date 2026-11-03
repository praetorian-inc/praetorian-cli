class RedTeamDeployment:
    """Direct, tenant-scoped access to the backend's safe deployment services.

    Authentication and selected-account headers come from the existing API
    client. Discovery never reads private details, state, tfvars, or artifacts.
    Human approval belongs to the CLI caller, not to this transport wrapper.
    """

    def __init__(self, api):
        self.api = api

    def inventory(self) -> dict:
        """Return authorized, redacted inventory and recorded operation history."""
        return self.api.get('red-team/deployment/inventory')

    def preview(self, request: dict) -> dict:
        """Prepare a safe, write-free preview of the requested lifecycle action."""
        return self.api.post('red-team/deployment/preview', request)

    def execute(self, request: dict, configuration_context_sha256: str) -> dict:
        """Submit the exact reviewed request with its server-computed context.

        Callers must obtain fresh human approval for every action except plan.
        A changed deployment, input, or infrastructure revision requires another
        preview; this method never retries execution or refreshes approval.
        """
        body = request | {
            'configuration_context_sha256': configuration_context_sha256,
        }
        return self.api.post('red-team/deployment/execute', body)

    def result(self, job_id: str, enqueued: str) -> dict:
        """Read one actual job run; retain both values from the enqueue result."""
        return self.api.get('red-team/deployment/results', params={
            'job_id': job_id,
            'enqueued': enqueued,
        })
