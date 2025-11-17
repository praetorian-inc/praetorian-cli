import json


class Jobs:
    """ The methods in this class are to be assessed from sdk.jobs, where sdk
    is an instance of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, target_key, capabilities=[], config=None, credentials=[]):
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
