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
    """ The methods in this class are to be assessed from sdk.statistics, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api
        self.util = Util

    def list(self, prefix_filter='', from_date=None, to_date=None, offset=None, pages=100000) -> tuple:
        """ List statistics with optional date range filtering """
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
        """ Make a single query with the given parameters """
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
        if isinstance(results, list):
            return results
        flattened = []
        for value in results.values():
            if isinstance(value, (list, dict)):
                flattened.extend(self._flatten_results(value))
        return flattened
