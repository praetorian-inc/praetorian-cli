import json
from time import sleep, time

from praetorian_cli.sdk.model.globals import AgentType


class Agents:

    def __init__(self, api):
        self.api = api

    def attribution(self, risk_key: str) -> str:
        self.api.agent(AgentType.ATTRIBUTION.value, dict(key=risk_key))

        # poll for the attribution job to complete
        job_key = self.api.jobs.system_job_key(AgentType.ATTRIBUTION.value, risk_key)

        start_time = time()
        while time() - start_time < 180:
            job = self.api.jobs.get(job_key)
            if self.api.jobs.is_failed(job):
                raise Exception('Attribution failed')
            if self.api.jobs.is_passed(job):
                break
            sleep(1)

        if self.api.jobs.is_passed(job):
            return self.attribution_result(risk_key)
        else:
            raise Exception('Timeout (3 minutes) waiting for attribution result.')

    def attribution_filename(self, agent_type: str, risk_key: str) -> str:
        return f'agents/{agent_type}/{risk_key}'

    def attribution_result(self, risk_key: str) -> dict:
        return json.loads(
            self.api.files.get(self.attribution_filename(AgentType.ATTRIBUTION.value, risk_key)).decode('utf-8'))
