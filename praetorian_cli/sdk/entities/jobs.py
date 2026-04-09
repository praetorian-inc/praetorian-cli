import json
import time


class Jobs:
    """ The methods in this class are to be assessed from sdk.jobs, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, target_key, capabilities=None, config=None, credentials=None):
        """
        Add a job to execute capabilities against an asset or attribute.

        Jobs are execution units that run security scanning capabilities
        against targets. Each job can execute multiple capabilities and can be
        configured with custom parameters. Jobs are queued for execution and
        their status can be monitored through the job lifecycle.

        :param target_key: The key of the target entity (asset or attribute)
            to run the job against
        :type target_key: str
        :param capabilities: List of capability names to execute (e.g.,
            ['nuclei', 'portscan', 'subdomain'])
        :type capabilities: list
        :param config: Optional JSON configuration string for capability
            parameters
        :type config: str or None
        :return: List of created job objects
        :rtype: list
        :raises Exception: If the config parameter contains invalid JSON
        :raises Exception: If an unknown capability is specified

        **Example Usage:**
            >>> # Add a basic job without specific capabilities (runs default
            >>> # scan)
            >>> jobs = sdk.jobs.add("#asset#example.com#1.2.3.4")

            >>> # Add a job with specific capabilities
            >>> jobs = sdk.jobs.add("#asset#example.com#1.2.3.4",
            >>>                      ["nuclei", "portscan"])

            >>> # Add a job with configuration
            >>> config = '{"run-type": "login", "timeout": 300}'
            >>> jobs = sdk.jobs.add("#asset#example.com#1.2.3.4", ["nuclei"],
            >>>                          config)

        **Job Object Structure:**
            Each job in the returned list contains:
            - key: Job identifier in format #job#{target}#{capability}
            - status: Current job status (JQ=queued, JR=running, JF=failed,
              JP=passed)
            - dns: DNS name from the target asset
            - capabilities: List of capabilities to execute
            - config: Configuration parameters (if provided)
            - created: Job creation timestamp

        **Common Capabilities:**
            - nuclei: Network vulnerability scanner
            - portscan: Port scanning capability
            - subdomain: Subdomain enumeration
            - crawler: Web application crawler
            - whois: Domain registration information lookup
        """
        body = dict(key=target_key)
        if capabilities:
            body = body | dict(capabilities=capabilities)

        if config:
            try:
                body = body | dict(config=json.loads(config))
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in configuration string: {e}")
            except Exception as e:
                raise Exception(f"Error processing configuration string: {e}")

        if credentials:
            body = body | dict(credential_ids=credentials)

        return self.api.force_add('job', body)

    def get(self, key):
        """
        Get details of a specific job by its key.

        :param key: The job key in format
            #job#{target}#{capability}#{timestamp}
        :type key: str
        :return: Job object with detailed information, or None if not found
        :rtype: dict or None

        **Example Usage:**
            >>> # Get a specific job
            >>> job = sdk.jobs.get(
            >>>     "#job#example.com#1.2.3.4#nuclei#1234567890")

        **Job Object Structure:**
            The returned job object contains:
            - key: Job identifier
            - status: Current status (JQ, JR, JF, JP)
            - dns: Target DNS name
            - capabilities: List of capabilities
            - config: Configuration parameters
            - created: Creation timestamp
            - updated: Last update timestamp
        """
        return self.api.search.by_exact_key(key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """
        List jobs, optionally filtered by key prefix.

        Retrieve jobs with optional filtering by the portion of the job key
        after '#job#'. This allows filtering by target DNS, IP address, or
        other key components.

        :param prefix_filter: Filter jobs by key prefix after '#job#' (e.g.,
            'example.com' to filter by DNS)
        :type prefix_filter: str
        :param offset: The offset for pagination to retrieve a specific page of
            results
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve (default: 100000
            for all results)
        :type pages: int
        :return: A tuple containing (list of matching jobs, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # List all jobs
            >>> jobs, offset = sdk.jobs.list()

            >>> # Filter jobs by DNS
            >>> jobs, offset = sdk.jobs.list("example.com")

            >>> # Get first page with pagination
            >>> jobs, offset = sdk.jobs.list("", None, 1)
            >>> # Get next page
            >>> jobs, offset = sdk.jobs.list("", offset, 1)

        **Job Status Monitoring:**
            Use this method to monitor job execution status:
            - JQ: Job is queued for execution
            - JR: Job is currently running
            - JF: Job failed during execution
            - JP: Job completed successfully
        """
        return self.api.search.by_key_prefix(f'#job#{prefix_filter}',
                                             offset, pages)

    def list_by_status(self, status, offset=None, pages=100000) -> tuple:
        """
        List jobs filtered by status code.

        Uses server-side filtering via DynamoDB Status GSI for efficient
        queries without fetching all jobs.

        :param status: Job status prefix to filter by
        :type status: str
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: A tuple containing (list of matching jobs, next page offset)
        :rtype: tuple

        **Status Codes:**
            - JQ: Job is queued for execution
            - JR: Job is currently running
            - JP: Job completed successfully
            - JF: Job failed during execution

        **Example Usage:**
            >>> # Find all running jobs
            >>> running, offset = sdk.jobs.list_by_status('JR')

            >>> # Find all failed jobs
            >>> failed, offset = sdk.jobs.list_by_status('JF')
        """
        return self.api.search.by_term(f'status:{status}', kind='job',
                                       offset=offset, pages=pages)

    def list_by_capability(self, capability, offset=None, pages=100000) -> tuple:
        """
        List jobs filtered by capability/scan type.

        Uses server-side filtering via DynamoDB Source GSI. The source
        field on jobs contains 'capability_name#timestamp', so begins_with
        matching on the capability name works correctly.

        :param capability: Capability name to filter by (e.g., 'nuclei',
            'portscan', 'diana-agent', 'julius')
        :type capability: str
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: A tuple containing (list of matching jobs, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # Find all nuclei scan jobs
            >>> nuclei_jobs, offset = sdk.jobs.list_by_capability('nuclei')

            >>> # Find all diana-agent jobs
            >>> diana_jobs, offset = sdk.jobs.list_by_capability('diana-agent')
        """
        return self.api.search.by_term(f'source:{capability}', kind='job',
                                       offset=offset, pages=pages)

    def list_by_target(self, target, offset=None, pages=100000) -> tuple:
        """
        List jobs filtered by target DNS or hostname.

        Uses server-side filtering via DynamoDB DNS GSI. This is a more
        explicit alternative to list(prefix_filter=target) for finding
        what jobs ran against a specific asset.

        :param target: Target DNS name or hostname to filter by
        :type target: str
        :param offset: The offset for pagination
        :type offset: str or None
        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: A tuple containing (list of matching jobs, next page offset)
        :rtype: tuple

        **Example Usage:**
            >>> # Find all jobs that targeted a specific domain
            >>> jobs, offset = sdk.jobs.list_by_target('api.example.com')
        """
        return self.list(prefix_filter=target, offset=offset, pages=pages)

    def summary(self, pages=100000) -> dict:
        """
        Return job counts grouped by capability and status.

        Fetches all jobs and aggregates counts client-side. This may be
        slow for accounts with many jobs (e.g., 90k+).

        :param pages: Maximum number of pages to retrieve
        :type pages: int
        :return: Dictionary with total count, counts by status, and counts
            by capability
        :rtype: dict

        **Example Usage:**
            >>> summary = sdk.jobs.summary()
            >>> print(summary['total'])
            91185
            >>> print(summary['by_capability'])
            {'nuclei': 4032, 'portscan': 1424, 'diana-agent': 5, ...}
            >>> print(summary['by_status'])
            {'JQ': 50000, 'JP': 30000, 'JR': 6, 'JF': 1000}
        """
        jobs, _ = self.list(pages=pages)
        summary = {
            'total': len(jobs),
            'by_status': {},
            'by_capability': {},
        }
        for job in jobs:
            status = job.get('status', 'unknown')
            status_code = status[:2] if len(status) >= 2 else status
            summary['by_status'][status_code] = summary['by_status'].get(status_code, 0) + 1

            source = job.get('source', 'unknown')
            capability = source.split('#')[0] if '#' in source else source
            if not capability:
                capability = 'unknown'
            summary['by_capability'][capability] = summary['by_capability'].get(capability, 0) + 1

        return summary

    def is_failed(self, job):
        """
        Check if a job has failed during execution.

        :param job: Job object to check (must contain 'status' field)
        :type job: dict or None
        :return: True if the job failed (status starts with 'JF'), False
            otherwise
        :rtype: bool

        **Example Usage:**
            >>> job = sdk.jobs.get(
            >>>     "#job#example.com#1.2.3.4#nuclei#1234567890")
            >>> if sdk.jobs.is_failed(job):
            >>>     print("Job execution failed")

        **Job Status Codes:**
            - JF: Job failed during execution
            - Other statuses (JQ, JR, JP) will return False
        """
        return job and job['status'] and job['status'].startswith('JF')

    def is_passed(self, job):
        """
        Check if a job has completed successfully.

        :param job: Job object to check (must contain 'status' field)
        :type job: dict or None
        :return: True if the job passed (status starts with 'JP'), False
            otherwise
        :rtype: bool

        **Example Usage:**
            >>> job = sdk.jobs.get(
            >>>     "#job#example.com#1.2.3.4#nuclei#1234567890")
            >>> if sdk.jobs.is_passed(job):
            >>>     print("Job completed successfully")

        **Job Status Codes:**
            - JP: Job completed successfully
            - Other statuses (JQ, JR, JF) will return False
        """
        return job and job['status'] and job['status'].startswith('JP')

    def bulk_results(self, job):
        """Download and parse per-item results for a completed bulk upsert job.

        Args:
            job: Job dict (must have 'config' with 'results_s3_key')

        Returns:
            Dict with 'summary' and 'results' keys, or None if job not complete.
        """
        if not self.is_passed(job) and not self.is_failed(job):
            return None
        results_key = job.get('config', {}).get('results_s3_key')
        if not results_key:
            return None
        content = self.api.files.get_utf8(results_key)
        return json.loads(content)

    def wait(self, job_key, poll_interval=5, timeout=3600):
        """Poll until a job completes or times out.

        Args:
            job_key: The job key to poll
            poll_interval: Seconds between polls (default 5)
            timeout: Max seconds to wait (default 3600)

        Returns:
            Final job dict

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                job = self.api.search.by_exact_key(job_key)
            except Exception:
                # Transient errors (504, 503, etc.) during polling are expected
                # when the backend is under load. Retry on next poll cycle.
                time.sleep(poll_interval)
                continue
            if job:
                if self.is_passed(job) or self.is_failed(job):
                    return job
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_key} did not complete within {timeout}s")

    def system_job_key(self, source, id):
        """
        Generate a system job key for internal job tracking.

        System jobs are internal jobs created by Chariot for system operations
        and maintenance tasks, distinct from user-initiated jobs.

        :param source: The source system or component that created the job
        :type source: str
        :param id: Unique identifier for the job within the source system
        :type id: str
        :return: Formatted system job key
        :rtype: str

        **Example Usage:**
            >>> # Generate a system job key
            >>> key = sdk.jobs.system_job_key("scheduler", "maintenance-001")
            >>> # Returns: "#job#maintenance-001#system#scheduler"

        **Key Format:**
            System job keys follow the format: #job#{id}#system#{source}
        """
        return f'#job#{id}#system#{source}'
