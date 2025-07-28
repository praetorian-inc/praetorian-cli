class Capabilities:
    """ The methods in this class are to be assessed from sdk.capabilities, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self, name='', target='', executor='') -> tuple:
        """
        List available capabilities, optionally filtered by name, target, and/or executor.

        Capabilities are security scanning tools and integrations available in Chariot.
        Each capability can target specific entity types (assets, attributes, preseeds, etc.)
        and run on different executors (chariot, aegis, janus).

        :param name: Filter capabilities by name (partial match, case-insensitive)
        :type name: str
        :param target: Filter capabilities by target type (exact match: asset, attribute, preseed, webpage, repository, integration)
        :type target: str
        :param executor: Filter capabilities by executor (partial match: chariot, aegis, janus)
        :type executor: str
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
            - name: Any string (partial matching)
        """
        return self.api.get('capabilities', {'name': name, 'target': target, 'executor': executor})
