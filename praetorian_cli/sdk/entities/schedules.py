"""SDK entity for capability schedules."""

import re
from typing import Optional

_SCHEDULE_ID_RE = re.compile(r'^[a-f0-9\-]+$', re.IGNORECASE)


def _validate_schedule_id(schedule_id: str) -> str:
    if not schedule_id or not _SCHEDULE_ID_RE.match(schedule_id):
        raise ValueError(f"Invalid schedule_id format: {schedule_id!r}")
    return schedule_id


class Schedules:
    """The methods in this class are to be accessed from sdk.schedules, where sdk
    is an instance of Chariot."""

    def __init__(self, api):
        self.api = api

    def list(self, pages=1) -> tuple:
        """
        List all capability schedules for the current user.

        Retrieves all scheduled capability executions, returning them with
        detailed information including schedule configuration, next execution
        time, and status.

        :param pages: Maximum number of pages to retrieve (default: 1)
        :type pages: int
        :return: A tuple containing (list of schedule objects, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all schedules
            >>> schedules, _ = sdk.schedules.list()

            >>> # Check schedule properties
            >>> for schedule in schedules:
            >>>     print(f"Schedule: {schedule['scheduleId']}")
            >>>     print(f"Capability: {schedule['capabilityName']}")
            >>>     print(f"Status: {schedule['status']}")
            >>>     print(f"Next: {schedule.get('nextExecution', 'N/A')}")

        **Schedule Object Properties:**
            - scheduleId: Unique identifier for the schedule
            - capabilityName: Name of the capability to execute
            - targetKey: Target asset key
            - status: Schedule status (active, paused, expired)
            - weeklySchedule: Weekly execution configuration
            - nextExecution: Next calculated execution time
            - lastExecution: Last execution timestamp
        """
        params = {'key': '#capability_schedule#'}
        resp = self.api.my(params, pages=pages)
        schedules = resp.get('capabilityschedules', [])
        offset = resp.get('offset')
        return schedules, offset

    def get(self, schedule_id: str) -> Optional[dict]:
        """
        Get a specific schedule by its ID.

        :param schedule_id: The unique schedule identifier
        :type schedule_id: str
        :return: Schedule object if found, None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> # Get specific schedule
            >>> schedule = sdk.schedules.get("abc123-def456")
            >>> if schedule:
            >>>     print(f"Found schedule: {schedule['capabilityName']}")
        """
        key = f'#capability_schedule#{schedule_id}'
        return self.api.search.by_exact_key(key)

    def create(self, capability_name: str, target_key: str, weekly_schedule: dict,
               start_date: str, end_date: str = None, config: dict = None,
               client_id: str = None) -> dict:
        """
        Create a new capability schedule.

        Creates a scheduled execution for a capability that will run on specified
        days and times.

        :param capability_name: Name of the capability to execute
        :type capability_name: str
        :param target_key: Target asset key (e.g., '#asset#hostname#hostname')
        :type target_key: str
        :param weekly_schedule: Weekly schedule configuration with day schedules
        :type weekly_schedule: dict
        :param start_date: Start date in RFC3339 format (e.g., '2024-01-15T00:00:00Z')
        :type start_date: str
        :param end_date: Optional end date in RFC3339 format
        :type end_date: str or None
        :param config: Optional capability configuration parameters
        :type config: dict or None
        :param client_id: Optional Aegis client ID for Aegis capabilities
        :type client_id: str or None
        :return: Created schedule object
        :rtype: dict

        **Example Usage:**
            >>> # Create a schedule that runs Monday and Friday at 10:00 UTC
            >>> weekly = {
            >>>     'monday': {'enabled': True, 'time': '10:00'},
            >>>     'tuesday': {'enabled': False, 'time': ''},
            >>>     'wednesday': {'enabled': False, 'time': ''},
            >>>     'thursday': {'enabled': False, 'time': ''},
            >>>     'friday': {'enabled': True, 'time': '10:00'},
            >>>     'saturday': {'enabled': False, 'time': ''},
            >>>     'sunday': {'enabled': False, 'time': ''}
            >>> }
            >>> schedule = sdk.schedules.create(
            >>>     capability_name='windows-smb-snaffler',
            >>>     target_key='#asset#server01#server01',
            >>>     weekly_schedule=weekly,
            >>>     start_date='2024-01-15T00:00:00Z'
            >>> )
        """
        body = {
            'capabilityName': capability_name,
            'targetKey': target_key,
            'weeklySchedule': weekly_schedule,
            'startDate': start_date,
        }
        if end_date:
            body['endDate'] = end_date
        if config:
            body['config'] = config
        if client_id:
            body['clientId'] = client_id

        return self.api.post('capability/schedule', body)

    def update(self, schedule_id: str, weekly_schedule: dict = None,
               start_date: str = None, end_date: str = None,
               config: dict = None) -> dict:
        """
        Update an existing schedule.

        :param schedule_id: The schedule ID to update
        :type schedule_id: str
        :param weekly_schedule: New weekly schedule configuration
        :type weekly_schedule: dict or None
        :param start_date: New start date in RFC3339 format
        :type start_date: str or None
        :param end_date: New end date in RFC3339 format (empty string to clear)
        :type end_date: str or None
        :param config: New capability configuration
        :type config: dict or None
        :return: Updated schedule object
        :rtype: dict

        **Example Usage:**
            >>> # Update schedule to run daily at 14:00
            >>> weekly = {
            >>>     'monday': {'enabled': True, 'time': '14:00'},
            >>>     'tuesday': {'enabled': True, 'time': '14:00'},
            >>>     # ... other days
            >>> }
            >>> schedule = sdk.schedules.update(
            >>>     schedule_id='abc123',
            >>>     weekly_schedule=weekly
            >>> )
        """
        schedule_id = _validate_schedule_id(schedule_id)
        body = {}
        if weekly_schedule is not None:
            body['weeklySchedule'] = weekly_schedule
        if start_date is not None:
            body['startDate'] = start_date
        if end_date is not None:
            body['endDate'] = end_date
        if config is not None:
            body['config'] = config

        return self.api.put(f'capability/schedule/{schedule_id}', body)

    def delete(self, schedule_id: str) -> None:
        """
        Delete a schedule.

        :param schedule_id: The schedule ID to delete
        :type schedule_id: str

        **Example Usage:**
            >>> # Delete a schedule
            >>> sdk.schedules.delete('abc123-def456')
        """
        schedule_id = _validate_schedule_id(schedule_id)
        self.api.delete(f'capability/schedule/{schedule_id}', {}, {})

    def pause(self, schedule_id: str) -> dict:
        """
        Pause a schedule.

        Temporarily stops a schedule from executing. The schedule can be resumed
        later with the resume() method.

        :param schedule_id: The schedule ID to pause
        :type schedule_id: str
        :return: Updated schedule object with paused status
        :rtype: dict

        **Example Usage:**
            >>> # Pause a schedule
            >>> schedule = sdk.schedules.pause('abc123-def456')
            >>> print(f"Status: {schedule['status']}")  # 'paused'
        """
        schedule_id = _validate_schedule_id(schedule_id)
        return self.api.patch(f'capability/schedule/{schedule_id}/pause')

    def resume(self, schedule_id: str) -> dict:
        """
        Resume a paused schedule.

        Reactivates a paused schedule so it will execute at the next scheduled time.

        :param schedule_id: The schedule ID to resume
        :type schedule_id: str
        :return: Updated schedule object with active status
        :rtype: dict

        **Example Usage:**
            >>> # Resume a paused schedule
            >>> schedule = sdk.schedules.resume('abc123-def456')
            >>> print(f"Status: {schedule['status']}")  # 'active'
        """
        schedule_id = _validate_schedule_id(schedule_id)
        return self.api.patch(f'capability/schedule/{schedule_id}/resume')
