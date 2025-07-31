class Util:
    """Helper class for building statistics filters"""

    # Main categories
    RISKS = "my#status"  # Risk statistics by status/severity
    RISK_EVENTS = "event#risk"  # Risk event statistics
    ASSETS_BY_STATUS = "asset#status"  # Asset statistics by status - NOTE this is just to differentiate from RISKS; the actual prefix is the same
    ASSETS_BY_CLASS = "class##asset##"  # Asset statistics by class
    SEEDS = "class##seed"  # Seed statistics by class

    # All possible risk statuses
    RISK_STATUSES = ["T", "O", "R", "I", "D"]

    # All possible asset statuses
    ASSET_STATUSES = ["A", "P", "D", "F", "AL", "AH"]

    @staticmethod
    def risks_by_status(status=None, severity=None):
        """Build filter for risk statistics by status and/or severity"""
        filter = "my#status"
        if status:
            filter += f":{status}"
            if severity:
                filter += f"#{severity}"
        return filter

    @staticmethod
    def get_statistics_help():
        """Returns simplified help text for statistics"""
        return """
    Available Statistics Filters:
    1. Risks & Status:
       --filter risks               : All risk statistics
       --filter risk_events         : All risk event statistics
       --filter "my#status:O#H"    : Open high severity risks
    2. Assets:
       --filter assets_by_status    : All asset statistics by status (A,P,D,F,AL,AH)
       --filter assets_by_class     : All asset statistics by class
       --filter seeds               : All seed statistics by class

    Examples:
    1. Current risk counts:
       $ praetorian chariot list statistics --filter risks --to now

    2. Risk event history:
       $ praetorian chariot list statistics --filter risk_events --from 2024-01-01

    3. Current asset status:
       $ praetorian chariot list statistics --filter assets_by_status --to now
    """


class Statistics:
    """
    Statistics entity manager for retrieving and analyzing statistical data from Chariot.

    This class provides methods to query various types of statistics including risk counts,
    asset statistics, event data, and other analytical information. Statistics can be
    filtered by date ranges and various criteria.

    The methods in this class are accessed from sdk.statistics, where sdk is an instance
    of Chariot.
    """

    def __init__(self, api):
        """
        Initialize the Statistics entity manager.

        :param api: The API client instance for making requests
        :type api: object
        """
        self.api = api
        self.util = Util

    def list(self, prefix_filter='', from_date=None, to_date=None, offset=None, pages=100000) -> tuple:
        """
        List statistics with optional date range filtering.

        :param prefix_filter: The filter prefix for statistics. Common values include 'risks', 'risk_events', 'assets_by_status', 'assets_by_class', 'seeds', or custom filters like 'my#status:O#H'
        :type prefix_filter: str
        :param from_date: Start date for filtering in YYYY-MM-DD format
        :type from_date: str or None
        :param to_date: End date for filtering in YYYY-MM-DD format
        :type to_date: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of statistics, next page offset)
        :rtype: tuple
        """
        # Handle the shorthands
        if prefix_filter == self.util.RISKS:
            all_stats = []
            for status in self.util.RISK_STATUSES:
                risk_filter = self.util.risks_by_status(status)
                stats, _ = self._query_single(risk_filter, from_date, to_date, offset, pages)
                all_stats.extend(stats)
            return all_stats, None
        elif prefix_filter == self.util.RISK_EVENTS:
            # events require double pounds before event type
            return self._query_single("event##risk#", from_date, to_date, offset, pages)
        elif prefix_filter == self.util.ASSETS_BY_STATUS:
            all_stats = []
            for status in self.util.ASSET_STATUSES:
                asset_filter = f"my#status:{status}"
                stats, _ = self._query_single(asset_filter, from_date, to_date, offset, pages)
                all_stats.extend(stats)
            return all_stats, None
        elif prefix_filter == self.util.ASSETS_BY_CLASS:
            return self._query_single("class##asset#", from_date, to_date, offset, pages)
        elif prefix_filter == self.util.SEEDS:
            return self._query_single("class##seed", from_date, to_date, offset, pages)
        else:
            return self._query_single(prefix_filter, from_date, to_date, offset, pages)

    def _query_single(self, prefix_filter, from_date, to_date, offset, pages):
        """
        Make a single query with the given parameters.

        :param prefix_filter: The filter prefix for the statistics query
        :type prefix_filter: str
        :param from_date: Start date for filtering in YYYY-MM-DD format
        :type from_date: str or None
        :param to_date: End date for filtering in YYYY-MM-DD format
        :type to_date: str or None
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of statistics, next page offset)
        :rtype: tuple
        """
        params = {}

        if from_date or to_date:
            base_key = f'#statistic#{prefix_filter}' if prefix_filter else '#statistic'
            if from_date:
                params['key'] = f'{base_key}#{from_date}'
            else:
                params['key'] = base_key
            if to_date:
                params['to'] = f'{base_key}#{to_date}'
            else:
                params['to'] = f'{base_key}#now'
        else:
            params['key'] = f'#statistic#{prefix_filter}'

        if offset:
            params['offset'] = offset

        results = self.api.my(params, pages)
        stats = self._flatten_results(results)

        next_offset = results.get('offset')
        return stats, next_offset

    def _flatten_results(self, results):
        """
        Flatten nested results into a single list.

        :param results: The results to flatten, can be a list or dictionary
        :type results: list or dict
        :return: A flattened list of results
        :rtype: list
        """
        if isinstance(results, list):
            return results
        flattened = []
        for value in results.values():
            if isinstance(value, (list, dict)):
                flattened.extend(self._flatten_results(value))
        return flattened
