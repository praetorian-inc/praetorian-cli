from praetorian_cli.handlers.utils import error
from praetorian_cli.sdk.model.globals import Seed, Kind
from praetorian_cli.sdk.model.query import Query, Node, Filter, KIND_TO_LABEL


class Seeds:
    """ The methods in this class are to be assessed from sdk.seeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, status=Seed.PENDING.value, seed_type=Kind.ASSET.value, **kwargs):
        """
        Add a seed of specified type with dynamic fields.
        
        :param status: Status for backward compatibility  
        :type status: str or None
        :param type: Asset type (e.g., 'asset', 'addomain', etc.)
        :type type: str
        :param kwargs: Dynamic fields for the asset type
        :return: The seed that was added
        :rtype: dict
        """
        # Handle status if provided
        kwargs['status'] = status
            
        # Build payload with type wrapper
        payload = {
            'type': seed_type,
            'model': kwargs
        }

        return self.api.upsert('seed', payload)

    def get(self, key):
        """
        Get details of a seed by key.

        :param key: Entity key (e.g., '#asset#example.com#example.com')
        :type key: str
        :return: The seed matching the specified key, or None if not found
        :rtype: dict or None
        """
        
        # Create a Filter for the key field
        key_filter = Filter(
            field=Filter.Field.KEY,
            operator=Filter.Operator.EQUAL,
            value=key
        )
        
        # Create a Node with Seed label and key filter
        node = Node(
            labels=[Node.Label.SEED],
            filters=[key_filter]
        )
        
        # Create the Query object
        query = Query(node=node)
        
        # Call by_query with the constructed Query object
        results_tuple = self.api.search.by_query(query)
        if not results_tuple:
            return None
        
        results, _ = results_tuple
        if len(results) == 0:
            return None
        return results[0]

    def update(self, key, status=None):
        """
        Update seed fields dynamically.
        
        :param key: Seed/Asset key (e.g., '#seed#domain#example.com' or '#asset#domain#example.com')
        :type key: str
        :param status: Status for backward compatibility (can be positional)
        :type status: str or None
        :param kwargs: Fields to update
        :return: The updated seed, or None if the seed was not found
        :rtype: dict or None
        """
            
        seed = self.get(key)  # This already handles old key format conversion
        if seed:
            update_payload = {
                'key': key,
                'status': status
            }
            
            return self.api.upsert('seed', update_payload)
        else:
            error(f'Seed {key} not found.')

    def delete(self, key):
        """
        Delete seed (supports both old and new key formats).
        
        :param key: Seed/Asset key (e.g., '#asset#domain#example.com')
        :type key: str
        :return: The seed that was marked as deleted, or None if the seed was not found
        :rtype: dict or None
        """
        seed = self.get(key)  # This already handles old key format conversion
        
        if seed:
            delete_payload = {
                'key': key,
                'status': Seed.DELETED.value
            }
            
            return self.api.upsert('seed', delete_payload)
        else:
            error(f'Seed {key} not found.')

    def list(self, seed_type=Kind.SEED.value, key_prefix='', pages=100000) -> tuple:
        """
        List seeds by querying assets with 'Seed' label.
        
        :param seed_type: Optional asset seed_type filter (e.g., 'asset', 'addomain')
        :seed_type seed_type: str or None
        :param key_prefix: Filter by key prefix
        :seed_type key_prefix: str
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :seed_type pages: int
        :return: A tuple containing (list of seeds, next page offset)
        :rseed_type: tuple
        """

        if seed_type in KIND_TO_LABEL:
            seed_type = KIND_TO_LABEL[seed_type]
        elif not seed_type:
            seed_type = Node.Label.SEED
        else:
            raise ValueError(f'Invalid seed type: {seed_type}')

        node = Node(
            labels=[seed_type],
            filters=[]
        )

        key_filter = Filter(
                field=Filter.Field.KEY,
                operator=Filter.Operator.STARTS_WITH,
                value=key_prefix
            )

        if key_prefix:
            node.filters.append(key_filter)
        
        query = Query(node=node)
        
        return self.api.search.by_query(query, pages)

    def attributes(self, key):
        """
        Get attributes associated with a seed.

        :param key: Entity key in format #seed#{type}#{dns} where type is 'domain', 'ip', or 'cidr' and dns is the seed value
        :type key: str
        :return: List of attributes associated with the seed
        :rtype: list
        """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes
