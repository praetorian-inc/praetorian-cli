CAPABILITY_ITEM_KEYS = ('capabilities', 'data', 'items')


def normalize_capabilities_response(result, item_keys=None):
    """Return capability dictionaries from Guard/list-compatible responses."""
    keys = item_keys or CAPABILITY_ITEM_KEYS
    if result is None:
        return []
    if isinstance(result, tuple):
        result = result[0] if result else []
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if isinstance(value, list):
                result = value
                break
            if isinstance(value, dict):
                result = list(value.values())
                break
        else:
            return []
    if not isinstance(result, list):
        return []
    return [capability for capability in result if isinstance(capability, dict)]


def capability_name(capability):
    if not isinstance(capability, dict):
        return ''
    return str(capability.get('name') or capability.get('Name') or '').strip()


def capability_description(capability):
    if not isinstance(capability, dict):
        return ''
    return str(capability.get('description') or capability.get('Description') or '')


def capability_target_type(capability, default='asset'):
    if not isinstance(capability, dict):
        return default
    target = capability.get('target', capability.get('Target', default))
    if isinstance(target, str):
        return target.lower()
    if isinstance(target, list):
        normalized = [str(item).lower() for item in target]
        return normalized[0] if normalized else default
    return str(target).lower()


class Capabilities:
    """ The methods in this class are to be assessed from sdk.capabilities, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self, name='', target='', executor='', endpoint_kind='') -> tuple:
        """
        List available capabilities, optionally filtered by name, target, executor, and/or endpoint kind.

        Capabilities are security scanning tools and integrations available in Chariot.
        Each capability can target specific entity types (assets, attributes, preseeds, etc.)
        and run on different executors (chariot, aegis, janus).

        :param name: Filter capabilities by name (partial match, case-insensitive)
        :type name: str
        :param target: Filter capabilities by target type (exact match: asset, attribute, preseed, webpage, repository, integration)
        :type target: str
        :param executor: Filter capabilities by executor (partial match: chariot, aegis, janus)
        :type executor: str
        :param endpoint_kind: Filter capabilities to those carried by an endpoint kind (e.g. aegis)
        :type endpoint_kind: str
        :return: A tuple containing (list of matching capabilities, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all capabilities
            >>> capabilities, offset = sdk.capabilities.list()
            
            >>> # Filter by name
            >>> capabilities, offset = sdk.capabilities.list(name='nuclei')
            
            >>> # Filter by target type
            >>> capabilities, offset = sdk.capabilities.list(target='asset')
            
            >>> # Filter by executor
            >>> capabilities, offset = sdk.capabilities.list(executor='chariot')
            
            >>> # Combine filters
            >>> capabilities, offset = sdk.capabilities.list(name='nuclei', target='attribute', executor='chariot')

        **Capability Object Structure:**
            Each capability in the returned list contains:
            - Name: Capability identifier (e.g., 'nuclei', 'subdomain')
            - Title: Human-readable title
            - Target: Target entity type (asset, attribute, preseed, etc.)
            - Description: Detailed capability description
            - Parameters: Configuration parameters for the capability
            - Integration: Whether this is an integration capability
            - Surface: Attack surface type (external, internal, cloud, repository)
            - Version: Capability version
            - Executor: Execution environment (chariot, aegis, janus)

        **Valid Filter Values:**
            - target: 'asset', 'attribute', 'preseed', 'webpage', 'repository', 'integration'
            - executor: 'chariot', 'aegis', 'janus'
            - endpoint_kind: 'aegis'
            - name: Any string (partial matching)
        """
        params = {'name': name, 'target': target, 'executor': executor}
        if endpoint_kind:
            params['endpoint_kind'] = endpoint_kind
        return self.api.get('capabilities', params)
