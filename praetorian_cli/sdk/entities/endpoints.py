ONLINE = 'online'


class Endpoints:
    """ The methods in this class are to be accessed from sdk.endpoints, where sdk is an
    instance of Chariot.

    Endpoints are Aegis v2 enrollments, which are a different inventory from the Aegis
    agents under sdk.aegis. An Aegis agent is identified by its client_id and reached
    over SSH; an endpoint is identified by its endpointId, holds a certificate issued at
    enrollment, and receives tasks dispatched by Guard. A mobile device running the Aegis
    agent is an endpoint, and never appears in the agent inventory.
    """

    def __init__(self, api):
        self.api = api

    def list(self, filter_text: str = '', online_only: bool = False, pages: int = 100) -> tuple:
        """
        List enrolled endpoints.

        :param filter_text: Filter endpoints by a case-insensitive substring of the endpoint
            ID, kind, hostname, OS, distribution or architecture
        :type filter_text: str
        :param online_only: If True, return only endpoints currently connected to Guard
        :type online_only: bool
        :param pages: Maximum number of result pages to retrieve. <mcp>Start with one page
            of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of endpoints, next page cursor)
        :rtype: tuple

        **Example Usage:**
            >>> endpoints, _ = sdk.endpoints.list()
            >>> for endpoint in endpoints:
            >>>     print(endpoint['endpointId'], endpoint['connectionState'])

            >>> # Only devices that can be dispatched to right now
            >>> ready, _ = sdk.endpoints.list(online_only=True)

        **Endpoint Object Properties:**
            - endpointId: Unique identifier, and what a job's endpoint_agent_id names
            - kind: Endpoint kind, e.g. 'aegis'
            - connectionState: 'online', 'not_connected' or 'revoked'
            - lifecycleState: Enrollment state of the endpoint's identity
            - profile: Reported system profile (hostname, os, distribution, kernel, arch)
            - taskDispatchPaused: True when Guard is holding tasks for this endpoint
            - enrolledAt / lastSeenAt: Enrollment and last-contact timestamps
        """
        endpoints = []
        cursor = ''

        for _ in range(max(pages, 1)):
            response = self.api.get('endpoint/list', dict(cursor=cursor) if cursor else {})
            endpoints.extend(response.get('endpoints') or [])
            cursor = response.get('cursor') or ''
            if not cursor:
                break

        if filter_text:
            endpoints = [e for e in endpoints if _matches(e, filter_text)]

        if online_only:
            endpoints = [e for e in endpoints if e.get('connectionState') == ONLINE]

        return endpoints, cursor

    def get(self, endpoint_id: str) -> dict:
        """
        Get a single enrolled endpoint by its ID.

        :param endpoint_id: The endpoint ID, as shown by sdk.endpoints.list()
        :type endpoint_id: str
        :return: The endpoint, or None if no endpoint is enrolled under that ID
        :rtype: dict or None

        **Example Usage:**
            >>> endpoint = sdk.endpoints.get('16169bc5-7943-4783-af81-c4735616f7e9')
            >>> if endpoint and endpoint['connectionState'] == 'online':
            >>>     print('ready to receive work')
        """
        # Paged through in full rather than filtered server-side: /endpoint/list takes no
        # id parameter, and a caller that reads "not enrolled" off a truncated first page
        # would be told something false about an endpoint that is enrolled and online.
        endpoints, _ = self.list()
        for endpoint in endpoints:
            if endpoint.get('endpointId') == endpoint_id:
                return endpoint
        return None


def _matches(endpoint: dict, filter_text: str) -> bool:
    profile = endpoint.get('profile') or {}
    fields = [
        endpoint.get('endpointId', ''),
        endpoint.get('kind', ''),
        endpoint.get('agentType', ''),
        profile.get('hostname', ''),
        profile.get('os', ''),
        profile.get('distribution', ''),
        profile.get('arch', ''),
    ]
    needle = filter_text.lower()
    return any(needle in str(field).lower() for field in fields)
