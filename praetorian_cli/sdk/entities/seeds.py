from praetorian_cli.handlers.utils import error
from praetorian_cli.sdk.model.globals import Seed, Kind


class Seeds:
    """ The methods in this class are to be assessed from sdk.seeds, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, dns, status=Seed.PENDING.value):
        """
        Add a seed to the account.

        :param dns: The DNS name, IP address, or CIDR range to add as a seed. Accepts domain names (e.g., 'example.com'), IP addresses (e.g., '192.168.1.1'), or CIDR ranges (e.g., '192.168.1.0/24')
        :type dns: str
        :param status: Seed status from Seed enum ('A' for Active, 'F' for Frozen, 'D' for Deleted, 'P' for Pending, 'FR' for Frozen Rejected)
        :type status: str
        :return: The seed that was added
        :rtype: dict
        """
        return self.api.upsert('seed', dict(dns=dns, status=status))

    def get(self, key):
        """
        Get details of a seed by key.

        :param key: Entity key in format #seed#{type}#{dns} where type is 'domain', 'ip', or 'cidr' and dns is the seed value
        :type key: str
        :return: The seed matching the specified key, or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key, False)

    def update(self, key, status):
        """
        Update a seed's status.

        Note: The seed PUT endpoint is different from other PUT endpoints. This method
        internally uses the DNS of the original seed rather than the key for the update operation.

        :param key: Entity key in format #seed#{type}#{dns} where type is 'domain', 'ip', or 'cidr' and dns is the seed value
        :type key: str
        :param status: Seed status from Seed enum ('A' for Active, 'F' for Frozen, 'D' for Deleted, 'P' for Pending, 'FR' for Frozen Rejected)
        :type status: str
        :return: The updated seed, or None if the seed was not found
        :rtype: dict or None
        """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # the seed PUT endpoint is different from other PUT endpoints. This one has to
            # take the DNS of the original seed, instead of the key of the seed record.
            # TODO, 2024-12-23, peter: check with Noah as to why. Ideally, we should
            # standardize to how other endpoints do it
            return self.api.upsert('seed', dict(dns=seed['dns'], status=status))
        else:
            error(f'Seed {key} is not found.')

    def delete(self, key):
        """
        Delete a seed by setting its status to DELETED.

        Note: This method does not actually delete the seed from the database. Instead,
        it sets the seed's status to DELETED ('D'), which marks it as deleted while
        preserving the record for audit purposes.

        :param key: Entity key in format #seed#{type}#{dns} where type is 'domain', 'ip', or 'cidr' and dns is the seed value
        :type key: str
        :return: The seed that was marked as deleted, or None if the seed was not found
        :rtype: dict or None
        """
        seed = self.api.search.by_exact_key(key)
        if seed:
            # TODO, 2024-12-23, peter: check with Noah why this is different from
            # deleting assets and risks
            return self.api.upsert('seed', dict(dns=seed['dns'], status=Seed.DELETED.value))
        else:
            error(f'Seed {key} is not found.')

    def list(self, type='', prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List seeds with optional filtering.

        :param type: The type of seed to filter by ('domain', 'ip', 'cidr'). If empty, returns all seed types
        :type type: str
        :param prefix_filter: Supply this to perform prefix-filtering of the seed DNS/IP values after the seed type portion of the key
        :type prefix_filter: str
        :param offset: The offset of the page you want to retrieve results. If this is not supplied, this function retrieves from the first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve
        :type pages: int
        :return: A tuple containing (list of seeds, next page offset)
        :rtype: tuple
        """
        prefix_term = '#seed#'
        if type:
            prefix_term = f'{prefix_term}{type}#'
        if prefix_filter:
            prefix_term = f'{prefix_term}{prefix_filter}'

        return self.api.search.by_key_prefix(prefix_term, offset, pages)

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
