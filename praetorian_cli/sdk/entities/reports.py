from datetime import date
from time import sleep, time


class Reports:
    """ The methods in this class are to be accessed from sdk.reports, where sdk
    is an instance of Chariot. """

    POLL_INTERVAL = 5
    DEFAULT_TIMEOUT = 300

    def __init__(self, api):
        self.api = api

    def customer_email(self):
        """
        Derive the customer email from the current SDK context.

        Uses the --account (assumed account) if set, otherwise falls back
        to the logged-in user's email. This mirrors the frontend logic of
        ``friend || me``.

        :return: The customer email address
        :rtype: str
        :raises Exception: If no customer email can be determined
        """
        email = self.api.keychain.account or self.api.keychain.username()
        if not email:
            raise Exception(
                'Could not determine customer email. '
                'Use --account or configure a username.'
            )
        return email

    def build_export_body(self, title, client_name, customer_email,
                          status_filter=('O', 'T'), risk_keys=(),
                          target='', start_date='', end_date='',
                          report_date='', draft=False, version='1.0',
                          export_format='pdf', group_by='attack_surface',
                          shared_output=False, executive_summary_path='',
                          narratives_path='', appendix_path=''):
        """
        Build the request body for POST /export/report.

        :param title: Report title
        :type title: str
        :param client_name: Client organization name
        :type client_name: str
        :param customer_email: Customer email address
        :type customer_email: str
        :param status_filter: Risk status codes to include
        :type status_filter: tuple or list
        :param risk_keys: Specific risk keys to include (empty for all)
        :type risk_keys: tuple or list
        :param target: Target/scope
        :type target: str
        :param start_date: Engagement start date (ISO format)
        :type start_date: str
        :param end_date: Engagement end date (ISO format)
        :type end_date: str
        :param report_date: Report date (ISO format). Defaults to today.
        :type report_date: str
        :param draft: Whether to add DRAFT watermark
        :type draft: bool
        :param version: Report version string
        :type version: str
        :param export_format: Output format ('pdf' or 'zip')
        :type export_format: str
        :param group_by: Finding grouping strategy ('attack_surface' or 'tag')
        :type group_by: str
        :param shared_output: Whether to copy to customer shared files
        :type shared_output: bool
        :param executive_summary_path: Path to executive summary .md in Guard storage
        :type executive_summary_path: str
        :param narratives_path: Path to narratives .md in Guard storage
        :type narratives_path: str
        :param appendix_path: Path to appendix .md in Guard storage
        :type appendix_path: str
        :return: Request body dict ready for POST /export/report
        :rtype: dict
        """
        if not report_date:
            report_date = date.today().isoformat()

        body = {
            'status_filter': list(status_filter),
            'config': {
                'title': title,
                'client_name': client_name,
                'report_date': report_date,
                'draft': draft,
                'version': version,
            },
            'shared_output': shared_output,
            'customer_email': customer_email,
            'export_format': export_format,
            'group_by': group_by,
        }

        if risk_keys:
            body['risk_keys'] = list(risk_keys)
        if target:
            body['config']['target'] = target
        if start_date:
            body['config']['start_date'] = start_date
        if end_date:
            body['config']['end_date'] = end_date
        if executive_summary_path:
            body['executive_summary_path'] = executive_summary_path
        if narratives_path:
            body['narratives_path'] = narratives_path
        if appendix_path:
            body['appendix_path'] = appendix_path

        return body

    def export(self, body, timeout=DEFAULT_TIMEOUT, poll_interval=POLL_INTERVAL):
        """
        Start a report export job, poll until completion, and return the job.

        :param body: Request body from build_export_body()
        :type body: dict
        :param timeout: Max seconds to wait for completion
        :type timeout: int
        :param poll_interval: Seconds between status polls
        :type poll_interval: int
        :return: The completed job dict
        :rtype: dict
        :raises Exception: If the job fails, times out, or no job key is returned
        """
        resp = self.api.post('export/report', body)

        job_key = resp.get('key')
        if not job_key:
            raise Exception('No job key returned from export/report endpoint.')

        return self.poll_job(job_key, timeout, poll_interval)

    def poll_job(self, job_key, timeout=DEFAULT_TIMEOUT, poll_interval=POLL_INTERVAL):
        """
        Poll a report generation job until it passes, fails, or times out.

        :param job_key: The job key to poll
        :type job_key: str
        :param timeout: Max seconds to wait
        :type timeout: int
        :param poll_interval: Seconds between polls
        :type poll_interval: int
        :return: The completed job dict
        :rtype: dict
        :raises Exception: If the job fails or times out
        """
        start_time = time()
        job = None
        while time() - start_time < timeout:
            job = self.api.jobs.get(job_key)
            if self.api.jobs.is_failed(job):
                message = job.get('message', 'unknown error')
                raise Exception(f'Report generation failed: {message}')
            if self.api.jobs.is_passed(job):
                return job
            sleep(poll_interval)

        raise Exception(f'Report generation timed out after {timeout} seconds.')

    def output_path(self, job):
        """
        Extract the output file path from a completed report job.

        :param job: The completed job dict
        :type job: dict
        :return: The output file path in Guard storage
        :rtype: str
        :raises Exception: If the output path cannot be determined
        """
        config = job.get('config', {})
        path = config.get('output') or job.get('dns', '')
        if not path:
            raise Exception('Could not determine output file path from job.')
        return path

    def download(self, job, download_directory):
        """
        Download the report file from a completed job to a local directory.

        :param job: The completed job dict
        :type job: dict
        :param download_directory: Local directory to save the file
        :type download_directory: str
        :return: The local file path where the report was saved
        :rtype: str
        """
        path = self.output_path(job)
        return self.api.files.save(path, download_directory)
