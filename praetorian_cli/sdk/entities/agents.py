from time import sleep, time

from praetorian_cli.sdk.model.globals import AgentType


class Agents:

    def __init__(self, api):
        self.api = api

    def affiliation(self, key, timeout=180) -> str:
        self.api.agent(AgentType.AFFILIATION.value, dict(key=key))

        # poll for the attribution job to complete
        job_key = self.api.jobs.system_job_key(AgentType.AFFILIATION.value, key)

        start_time = time()
        while time() - start_time < timeout:
            job = self.api.jobs.get(job_key)
            if self.api.jobs.is_failed(job):
                raise Exception('Failed to retrieve affiliation data.')
            if self.api.jobs.is_passed(job):
                break
            sleep(1)

        if self.api.jobs.is_passed(job):
            return self.affiliation_result(key)
        else:
            raise Exception(f'Timeout waiting for affiliation result ({timeout} seconds).')

    def affiliation_filename(self, agent_type: str, key: str) -> str:
        return f'agents/{agent_type}/{key}'

    def affiliation_result(self, key: str) -> dict:
        return self.api.files.get_utf8(self.affiliation_filename(AgentType.AFFILIATION.value, key))
