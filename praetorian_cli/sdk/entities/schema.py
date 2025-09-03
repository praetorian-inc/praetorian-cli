class Schema:
    """Access Chariot entity schemas via the SDK.

    Methods in this class are accessed from `sdk.schema`, where `sdk` is an
    instance of `Chariot`.
    """

    def __init__(self, api):
        self.api = api

    def get(self, entity_type: str | None = None) -> dict:
        """Get schema information for entity types.

        Args:
            entity_type: Optional specific entity type. If provided and it exists,
                only that schema is returned. If not provided, all schemas are returned.

        Returns:
            dict: Schema information.
        """
        result = self.api.get('schema', )
        if entity_type:
            if entity_type not in result:
                return {}
            return {entity_type: result[entity_type]}
        return result

