import json

class Jobs:
    """ The methods in this class are to be assessed from sdk.jobs, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, target_key, capabilities=[], config=None):
        """ Add a job for an asset or an attribute """
        params = dict(key=target_key)
        if capabilities:
            params = params | dict(capabilities=capabilities)
        
        if config:
            try:
                params = params | dict(config=json.loads(config))
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in configuration string: {e}")
            except Exception as e:
                raise Exception(f"Error processing configuration string: {e}")
                
        return self.api.force_add('job', params)

    def get(self, key):
        """ Get details of a job """
        return self.api.search.by_exact_key(key)

    def list(self, prefix_filter='', offset=None, pages=100000) -> tuple:
        """ List jobs, optionally prefix-filtered by the portion of the key after
            '#job#' """
        return self.api.search.by_key_prefix(f'#job#{prefix_filter}', offset, pages)

    def is_failed(self, job):
        return job and job['status'] and job['status'].startswith('JF')

    def is_passed(self, job):
        return job and job['status'] and job['status'].startswith('JP')

    def system_job_key(self, source, id):
        return f'#job#{id}#system#{source}'
